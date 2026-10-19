import asyncio
import hashlib
import html
import json
import re
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from .errors import AppError
from .generation import Generator
from .jobs import JobReader, PublicJobTransport
from .models import GenerateRequest, PairRequest, Profile, ResumeRequest
from .resumes import read_resume
from .oauth import OAuth
from .storage import Vault, default_data_dir

ORIGIN_PATTERN = re.compile(r"^chrome-extension://[a-p]{32}$")


@dataclass
class Settings:
    data_dir: Path
    port: int = 1455
    demo: bool = False


class LocalGuard:
    def __init__(self, app, owner):
        self.app = app
        self.owner = owner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        original_send = send

        async def private_send(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [
                    *[(key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"],
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                ]}
            await original_send(message)
        send = private_send
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode()
        allowed_host = f"127.0.0.1:{self.owner.state.settings.port}"
        if host != allowed_host:
            return await JSONResponse({"message": "Invalid local host."}, status_code=403)(scope, receive, send)
        origin = headers.get(b"origin", b"").decode()
        extension_id = headers.get(b"x-composer-extension", b"").decode()
        if origin and not ORIGIN_PATTERN.fullmatch(origin):
            return await JSONResponse({"message": "This origin is not allowed."}, status_code=403)(scope, receive, send)
        if extension_id and (not re.fullmatch(r"[a-p]{32}", extension_id) or (origin and origin != "chrome-extension://" + extension_id)):
            return await JSONResponse({"message": "Invalid extension identity."}, status_code=403)(scope, receive, send)
        # Privileged extension fetches can omit Origin. The pairing token is the
        # credential; a claimed ID never authorizes access without that token.
        if not origin and extension_id:
            origin = "chrome-extension://" + extension_id
        path = scope["path"]
        pairing = self.owner.state.vault.state.get("pairing", {})
        public_path = path in ("/health", "/auth/callback")
        valid_extension = bool(ORIGIN_PATTERN.fullmatch(origin))
        if scope["method"] == "OPTIONS":
            if not valid_extension or (pairing and origin != pairing.get("origin")):
                return await Response(status_code=403)(scope, receive, send)
            return await self.app(scope, receive, send)
        if not public_path:
            if not valid_extension:
                return await JSONResponse({"message": "Open the Chrome extension."}, status_code=403)(scope, receive, send)
            if path != "/pair":
                raw_token = headers.get(b"x-composer-token", b"").decode()
                digest = hashlib.sha256(raw_token.encode()).hexdigest()
                if origin != pairing.get("origin") or not secrets.compare_digest(digest, pairing.get("token_hash", "")):
                    return await JSONResponse({"code": "pairing_required", "message": "Pair the extension with your companion."}, status_code=401)(scope, receive, send)
        if scope["method"] in ("POST", "PUT"):
            length = headers.get(b"content-length", b"")
            body_limit = 8 * 1024 * 1024 if path == "/resume/import" else 131072
            if not length.isdigit() or int(length) > body_limit:
                return await JSONResponse({"message": "Request body is missing a size or too large."}, status_code=413)(scope, receive, send)
            if headers.get(b"content-type", b"").split(b";")[0] != b"application/json":
                return await JSONResponse({"message": "Use a JSON request."}, status_code=415)(scope, receive, send)
        return await self.app(scope, receive, send)


def create_app(settings: Settings | None = None, *, transport=None, job_transport=None, key: bytes | None = None) -> FastAPI:
    settings = settings or Settings(default_data_dir())
    vault = Vault(settings.data_dir, key)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            transport=transport, timeout=httpx.Timeout(120, connect=15),
            follow_redirects=False, trust_env=False,
        ) as client, httpx.AsyncClient(
            transport=PublicJobTransport(job_transport), timeout=httpx.Timeout(10, connect=8),
            follow_redirects=False, trust_env=False,
        ) as job_client:
            app.state.oauth = OAuth(vault, client, settings.port)
            app.state.generator = Generator(client, app.state.oauth, settings.demo, JobReader(job_client))
            app.state.generation_lock = asyncio.Lock()
            app.state.resume_lock = asyncio.Lock()
            yield

    app = FastAPI(title="draft-kit Companion", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.vault = vault
    app.state.pair_code = secrets.token_urlsafe(18)
    app.state.pair_expires = time.time() + 600
    app.state.pair_failures = 0
    app.add_middleware(
        CORSMiddleware, allow_origin_regex=ORIGIN_PATTERN.pattern,
        allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Composer-Token", "X-Composer-Extension"],
        allow_credentials=False,
    )
    app.add_middleware(LocalGuard, owner=app)

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse({"code": error.code, "message": error.message}, status_code=error.status)

    @app.exception_handler(httpx.HTTPError)
    async def network_error(request, error):
        return JSONResponse({"code": "network_error", "message": "Could not reach ChatGPT. Check your internet connection."}, status_code=502)

    # FastAPI's default validation response includes input values; do not echo
    # prompts, pairing codes or private job data in error responses.
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"code": "validation_error", "message": "Some fields are missing or too long. Check your inputs."}, status_code=422)

    @app.get("/health")
    async def health():
        return {"ok": True, "app": "draft-kit", "version": "0.9.0", "mode": "demo" if settings.demo else "chatgpt"}

    @app.post("/pair")
    async def pair(body: PairRequest, request: Request):
        origin = request.headers.get("origin") or "chrome-extension://" + request.headers.get("x-composer-extension", "")
        if origin != "chrome-extension://" + body.extension_id:
            raise AppError("pairing_invalid", "The extension identity did not match.", 403)
        if app.state.pair_failures >= 10:
            raise AppError("pairing_locked", "Restart the companion to get a fresh pairing code.", 429)
        if time.time() > app.state.pair_expires:
            raise AppError("pairing_expired", "This pairing code expired. Restart the companion.", 400)
        if not secrets.compare_digest(body.code, app.state.pair_code):
            app.state.pair_failures += 1
            raise AppError("pairing_invalid", "That pairing code did not match.", 401)
        token = secrets.token_urlsafe(32)
        vault.state["pairing"] = {"origin": origin, "token_hash": hashlib.sha256(token.encode()).hexdigest()}
        vault.save()
        app.state.pair_expires = 0
        return {"pair_token": token}

    @app.get("/auth/status")
    async def auth_status():
        return {**app.state.oauth.status(), "mode": "demo" if settings.demo else "chatgpt"}

    @app.post("/auth/start")
    async def auth_start():
        if settings.demo:
            raise AppError("demo_mode", "Restart the companion without --demo to connect ChatGPT.")
        return {"url": await app.state.oauth.start()}

    @app.get("/auth/callback")
    async def auth_callback(request: Request):
        try:
            await app.state.oauth.callback(dict(request.query_params))
            message = "Connected. Return to draft-kit in Chrome."
            status = 200
        except AppError as error:
            message, status = error.message, error.status
        return HTMLResponse(
            "<!doctype html><html><head><meta charset='utf-8'><title>draft-kit</title></head>"
            "<body><h1>draft-kit</h1><p>" + html.escape(message) + "</p></body></html>",
            status_code=status,
            headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'", "Referrer-Policy": "no-referrer"},
        )

    @app.post("/auth/logout")
    async def logout():
        revoked = await app.state.oauth.logout()
        return {
            "remote_revocation_confirmed": revoked,
            "message": "Disconnected." if revoked else "Disconnected locally. Remote revocation was not confirmed; disconnect the app in ChatGPT Settings too.",
        }

    @app.get("/models")
    async def models():
        return {"models": await app.state.generator.models()}

    @app.get("/profile")
    async def profile():
        return vault.profile().model_dump()

    @app.put("/profile")
    async def put_profile(body: Profile):
        vault.put_profile(body)
        return body.model_dump()

    @app.delete("/profile")
    async def clear_profile():
        vault.state.pop("profile", None)
        vault.save()
        return {"ok": True}

    @app.post("/resume/import")
    async def import_resume(body: ResumeRequest):
        lock = app.state.resume_lock
        if lock.locked():
            raise AppError("resume_busy", "A résumé is being read. Wait a moment.", 409)
        await lock.acquire()
        try:
            return await read_resume(body.filename, body.content_base64)
        finally:
            lock.release()

    @app.post("/generate")
    async def generate(body: GenerateRequest):
        lock = app.state.generation_lock
        # There is no await between the check and acquisition on this event loop.
        if lock.locked():
            raise AppError("busy", "A draft is already being generated. Wait or cancel it first.", 409)
        await lock.acquire()
        current_profile = vault.profile()

        async def stream():
            try:
                async for event in app.state.generator.generate(current_profile, body):
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except AppError as error:
                yield json.dumps({"type": "error", "code": error.code, "message": error.message}) + "\n"
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                yield json.dumps({"type": "error", "code": "generation_failed", "message": "The request could not finish. Your partial draft is preserved."}) + "\n"
            finally:
                lock.release()

        return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})

    return app
