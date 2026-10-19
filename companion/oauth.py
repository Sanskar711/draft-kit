import asyncio
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

from .errors import AppError, provider_error
from .storage import Vault

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
USAGE_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke " + USAGE_SCOPE
DISCOVERY = ISSUER + "/.well-known/openid-configuration"


class OAuth:
    def __init__(self, vault: Vault, client: httpx.AsyncClient, port: int):
        self.vault = vault
        self.client = client
        self.redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
        self.pending: dict | None = None
        self.last_error = ""
        self.lock = asyncio.Lock()
        self._metadata: dict | None = None
        self._keys: dict | None = None

    async def metadata(self) -> dict:
        if self._metadata is None:
            response = await self.client.get(DISCOVERY, timeout=15)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise AppError("discovery_invalid", "OpenAI identity configuration could not be verified.", 502)
            if data.get("issuer") != ISSUER:
                raise AppError("discovery_invalid", "OpenAI identity configuration could not be verified.", 502)
            for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                self._trusted_endpoint(data.get(field))
            if data.get("revocation_endpoint"):
                self._trusted_endpoint(data["revocation_endpoint"])
            self._metadata = data
        return self._metadata

    @staticmethod
    def _trusted_endpoint(url):
        parsed = urlsplit(url or "")
        if parsed.scheme != "https" or parsed.netloc != "auth.openai.com" or parsed.username:
            raise AppError("discovery_invalid", "Unexpected OpenAI identity endpoint.", 502)

    def status(self) -> dict:
        registration = self.vault.state.get("registration", {})
        tokens = registration.get("tokens", {})
        permitted = USAGE_SCOPE in tokens.get("scopes", [])
        return {
            "connected": bool(tokens.get("access_token")),
            "plan_enabled": bool(tokens.get("access_token")) and permitted,
            "email": registration.get("email", ""),
            "pending": bool(self.pending and self.pending["expires_at"] > time.time()),
            "error": self.last_error,
        }

    async def start(self) -> str:
        async with self.lock:
            metadata = await self.metadata()
            registration = self.vault.state.get("registration", {})
            client_id = registration.get("client_id", "dynamic_agent_client")
            verifier = secrets.token_urlsafe(64)
            self.pending = {
                "state": secrets.token_urlsafe(32),
                "nonce": secrets.token_urlsafe(32),
                "verifier": verifier,
                "client_id": client_id,
                "subject": registration.get("subject"),
                "expires_at": time.time() + 600,
            }
            self.last_error = ""
            params = {
                "client_id": client_id,
                "ext_agent_host_id": self.vault.state["host_id"],
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": SCOPES,
                "resource": RESOURCE,
                "state": self.pending["state"],
                "nonce": self.pending["nonce"],
                "code_challenge_method": "S256",
                "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("="),
            }
            if client_id == "dynamic_agent_client":
                params["agent_name_hint"] = "draft-kit"
            elif registration.get("email"):
                params["login_hint"] = registration["email"]
            return metadata["authorization_endpoint"] + "?" + urlencode(params)

    async def verify_identity(self, encoded: str, client_id: str, nonce: str) -> dict:
        metadata = await self.metadata()
        try:
            header = jwt.get_unverified_header(encoded)
            if header.get("alg") not in ("RS256", "ES256") or not header.get("kid"):
                raise ValueError("Unsupported signature")
            if self._keys is None or not any(k.get("kid") == header["kid"] for k in self._keys.get("keys", [])):
                response = await self.client.get(metadata["jwks_uri"], timeout=15)
                response.raise_for_status()
                self._keys = response.json()
            selected = next(k for k in self._keys["keys"] if k.get("kid") == header["kid"])
            key = jwt.PyJWK.from_dict(selected).key
            claims = jwt.decode(
                encoded, key, algorithms=["RS256", "ES256"], audience=client_id,
                issuer=ISSUER, leeway=5,
                options={"require": ["exp", "iat", "sub", "iss", "aud", "nonce"]},
            )
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise ValueError("Missing subject")
            if not isinstance(claims["nonce"], str) or not secrets.compare_digest(claims["nonce"], nonce):
                raise ValueError("Nonce mismatch")
            return claims
        except (jwt.PyJWTError, ValueError, KeyError, StopIteration):
            raise AppError("identity_invalid", "ChatGPT identity could not be verified. Start a new sign-in.", 401) from None

    @staticmethod
    def token_record(data: dict, previous: dict | None = None) -> dict:
        previous = previous or {}
        if not isinstance(data, dict):
            raise AppError("tokens_invalid", "ChatGPT returned an invalid credential response.", 502)
        if not isinstance(data.get("access_token"), str) or not data["access_token"]:
            raise AppError("tokens_invalid", "ChatGPT did not return an access token.", 502)
        if data.get("token_type", "").lower() != "bearer":
            raise AppError("tokens_invalid", "ChatGPT returned an unsupported token type.", 502)
        scopes = data.get("scope")
        if scopes is None:
            scope_list = previous.get("scopes", [])
        elif isinstance(scopes, str):
            scope_list = scopes.split()
        else:
            raise AppError("tokens_invalid", "ChatGPT permissions could not be verified.", 502)
        try:
            expires_in = int(data["expires_in"])
            earliest = float(data.get("earliest_refresh_at") or 0)
            if not 0 < expires_in <= 86400 or not __import__("math").isfinite(earliest):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise AppError("tokens_invalid", "ChatGPT token expiry could not be verified.", 502) from None
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", previous.get("refresh_token", "")),
            "id_token": data.get("id_token", previous.get("id_token", "")),
            "scopes": scope_list,
            "expires_at": time.time() + expires_in,
            "earliest_refresh_at": earliest,
        }

    async def callback(self, query: dict) -> None:
        async with self.lock:
            transaction = self.pending
            state = query.get("state", "")
            if not transaction or transaction["expires_at"] <= time.time():
                raise AppError("state_invalid", "This sign-in expired or was already used. Start again.", 400)
            if not secrets.compare_digest(state, transaction["state"]):
                raise AppError("state_invalid", "This sign-in could not be verified. Start again.", 400)
            # Consume only a verified transaction, before any network request.
            self.pending = None
            try:
                if query.get("error"):
                    raise AppError("access_denied", "Sign-in was cancelled. You can try again.", 400)
                code = query.get("code", "")
                client_id = query.get("client_id", "")
                if transaction["client_id"] == "dynamic_agent_client":
                    if not client_id or client_id == "dynamic_agent_client":
                        raise AppError("client_invalid", "Registration did not return a client ID.", 400)
                else:
                    if client_id and client_id != transaction["client_id"]:
                        raise AppError("client_invalid", "The returned registration did not match your account.", 400)
                    client_id = transaction["client_id"]
                if not code or len(code) > 8192 or len(client_id) > 256:
                    raise AppError("code_invalid", "The sign-in callback was incomplete.", 400)
                metadata = await self.metadata()
                response = await self.client.post(metadata["token_endpoint"], data={
                    "grant_type": "authorization_code", "client_id": client_id, "code": code,
                    "code_verifier": transaction["verifier"], "redirect_uri": self.redirect_uri,
                    "resource": RESOURCE,
                }, timeout=20)
                if response.status_code != 200:
                    raise AppError("exchange_failed", "ChatGPT sign-in failed. Start a fresh sign-in.", 401)
                data = response.json()
                identity = await self.verify_identity(data.get("id_token", ""), client_id, transaction["nonce"])
                if transaction.get("subject") and identity["sub"] != transaction["subject"]:
                    raise AppError("account_mismatch", "This registration belongs to a different ChatGPT account.", 401)
                tokens = self.token_record(data)
                self.vault.state["registration"] = {
                    "client_id": client_id, "subject": identity["sub"],
                    "issuer": identity["iss"], "email": identity.get("email", ""),
                    "tokens": tokens,
                }
                self.vault.save()
                if USAGE_SCOPE not in tokens["scopes"]:
                    self.last_error = "Signed in, but ChatGPT plan-usage permission was not granted. Reconnect to enable it."
            except AppError as error:
                self.last_error = error.message
                raise
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                self.last_error = "ChatGPT sign-in could not finish. Check your connection and try again."
                raise AppError("sign_in_failed", self.last_error, 502) from None

    async def access_token(self) -> str:
        async with self.lock:
            registration = self.vault.state.get("registration", {})
            tokens = registration.get("tokens", {})
            if not tokens.get("access_token") or USAGE_SCOPE not in tokens.get("scopes", []):
                raise AppError("sign_in_required", "Connect ChatGPT and allow plan usage first.", 401)
            now = time.time()
            if tokens.get("expires_at", 0) > now + 60:
                return tokens["access_token"]
            if tokens.get("earliest_refresh_at", 0) > now and tokens.get("expires_at", 0) > now:
                return tokens["access_token"]
            if not tokens.get("refresh_token"):
                raise AppError("sign_in_required", "Reconnect ChatGPT to renew your session.", 401)
            metadata = await self.metadata()
            response = await self.client.post(metadata["token_endpoint"], data={
                "grant_type": "refresh_token", "client_id": registration["client_id"],
                "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
            }, timeout=20)
            if response.status_code != 200:
                if response.status_code in (400, 401, 403):
                    registration.pop("tokens", None)
                    self.vault.save()
                    self.last_error = "Your ChatGPT session expired. Reconnect to continue."
                    raise AppError("sign_in_required", self.last_error, 401)
                raise provider_error(response.status_code)
            refreshed = self.token_record(response.json(), tokens)
            registration["tokens"] = refreshed
            self.vault.save()
            if USAGE_SCOPE not in refreshed["scopes"]:
                raise AppError("sign_in_required", "ChatGPT plan-usage permission is no longer enabled.", 401)
            return refreshed["access_token"]

    async def logout(self) -> bool:
        async with self.lock:
            registration = self.vault.state.get("registration", {})
            refresh = registration.get("tokens", {}).get("refresh_token")
            revoked = not bool(refresh)
            try:
                if refresh:
                    metadata = await self.metadata()
                    if metadata.get("revocation_endpoint"):
                        for attempt in range(2):
                            response = await self.client.post(metadata["revocation_endpoint"], data={
                                "token": refresh, "token_type_hint": "refresh_token",
                                "client_id": registration["client_id"],
                            }, timeout=5)
                            revoked = response.status_code == 200
                            if revoked or response.status_code < 500:
                                break
                            await asyncio.sleep(0.2 * (attempt + 1))
            except (httpx.HTTPError, AppError, ValueError):
                pass
            finally:
                registration.pop("tokens", None)
                self.pending = None
                self.last_error = ""
                self.vault.save()
            return revoked
