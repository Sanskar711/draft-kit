import asyncio
import json
import socket

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from companion import jobs
from companion.app import Settings, create_app
from companion.errors import AppError

JOB = {
    "@type": "JobPosting", "title": "Backend Engineer",
    "hiringOrganization": {"name": "Example Labs"},
    "jobLocation": {"address": {"addressLocality": "Bengaluru", "addressCountry": "IN"}},
    "description": "<p>Build Python and FastAPI services, RabbitMQ consumers and reliable payment webhooks.</p><p>Requirements: 1–2 years of backend experience.</p>",
    "skills": "Python, FastAPI, MongoDB, RabbitMQ",
}


def html_for(value=JOB):
    return '<html><head><title>Jobs</title><script type="application/ld+json">' + json.dumps({"@graph": [value]}) + '</script></head><body><nav>Other jobs</nav><main>Listing</main></body></html>'


@pytest.mark.parametrize("url", [
    "http://jobs.example.com/one", "https://127.0.0.1/", "https://[::1]/", "https://localhost/",
    "https://169.254.169.254/", "https://jobs.example.com:8443/", "https://user:secret@jobs.example.com/",
    "https://jobs.local/", "https://jobs.internal/", "file:///tmp/job", "https://jobs.example.com/with space",
    "https://jobs.example.com\\@127.0.0.1/",
    "https://224.0.0.1/", "https://[ff02::1]/",
    "https://www.linkedin.com/in/alex-rao/",
])
def test_invalid_job_urls(url):
    with pytest.raises(AppError):
        jobs.job_url(url)


def test_job_posting_extraction_and_plain_text_fallback():
    result = jobs.extract_job(html_for(), "https://jobs.example.com/one")
    assert result["title"] == "Backend Engineer"
    assert result["company"] == "Example Labs"
    assert result["location"] == "Bengaluru, IN"
    assert "1–2 years" in result["description"] and "RabbitMQ" in result["description"]
    assert "Other jobs" not in result["description"] and "<p>" not in result["description"]
    plain = '<title>Backend role at Example</title><nav>Wrong role</nav><main><h1>Backend role</h1><h2>Requirements</h2><p>' + "Build reliable Python APIs and distributed backend services. " * 4 + '</p><script>secret</script></main>'
    result = jobs.extract_job(plain, "https://jobs.example.com/one")
    assert result["warnings"] and "Wrong role" not in result["description"] and "secret" not in result["description"]


def test_ambiguous_and_blocked_pages_do_not_become_role_details():
    with pytest.raises(AppError, match="several roles"):
        jobs.extract_job(html_for({"@type": "ItemList", "itemListElement": [JOB, JOB]}), "https://jobs.example.com/")
    with pytest.raises(AppError, match="Paste the job description"):
        jobs.extract_job('<title>Login</title><main>Sign in to view this job. Requirements ' + "Sign in now. " * 20 + '</main>', "https://jobs.example.com/")


def test_dns_rejects_mixed_public_and_private_answers(monkeypatch):
    def answer(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)) for address in ("93.184.216.34", "127.0.0.1")]
    monkeypatch.setattr(socket, "getaddrinfo", answer)
    with pytest.raises(AppError, match="public job link"):
        asyncio.run(jobs.public_address("jobs.example.com"))


@pytest.fixture
def public_dns(monkeypatch):
    async def address(host):
        assert host in {"jobs.example.com", "careers.example.com"}
        return "93.184.216.34"
    monkeypatch.setattr(jobs, "public_address", address)


def test_lookup_pins_dns_and_never_forwards_cookies_or_credentials(public_dns):
    requests = []
    def page(request):
        requests.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.extensions["sni_hostname"] in {"jobs.example.com", "careers.example.com"}
        assert "authorization" not in request.headers and "cookie" not in request.headers
        if request.headers["host"] == "jobs.example.com":
            return httpx.Response(302, headers={"location": "https://careers.example.com/role", "set-cookie": "tracking=private"})
        return httpx.Response(200, text=html_for(), headers={"content-type": "text/html; charset=utf-8"})
    async def run():
        async with httpx.AsyncClient(transport=jobs.PublicJobTransport(httpx.MockTransport(page)), follow_redirects=False, trust_env=False) as client:
            client.cookies.set("login", "private")
            client.headers["Authorization"] = "Bearer private-test-token"
            result = await jobs.JobReader(client).lookup("https://jobs.example.com/role")
            assert result["url"] == "https://careers.example.com/role"
    asyncio.run(run())
    assert len(requests) == 2


@pytest.mark.parametrize("kind", ["private_redirect", "blocked", "oversize", "non_html", "redirect_loop"])
def test_lookup_fails_with_actionable_errors(public_dns, kind):
    def page(request):
        if kind == "private_redirect":
            return httpx.Response(302, headers={"location": "https://127.0.0.1/secret"})
        if kind == "blocked":
            return httpx.Response(403, text="Private provider details")
        if kind == "non_html":
            return httpx.Response(200, json={"secret": "private"})
        if kind == "redirect_loop":
            return httpx.Response(302, headers={"location": "/loop"})
        return httpx.Response(200, content=b"x" * (jobs.MAX_PAGE + 1), headers={"content-type": "text/html"})
    async def run():
        async with httpx.AsyncClient(transport=jobs.PublicJobTransport(httpx.MockTransport(page)), follow_redirects=False, trust_env=False) as client:
            with pytest.raises(AppError) as failure:
                await jobs.JobReader(client).lookup("https://jobs.example.com/role")
            assert "private" not in failure.value.message.lower()
    asyncio.run(run())


def test_job_link_stream_includes_details_and_relevant_profile_fact(tmp_path, public_dns):
    def page(request):
        return httpx.Response(200, text=html_for(), headers={"content-type": "text/html"})
    app = create_app(Settings(tmp_path / "data", demo=True), job_transport=httpx.MockTransport(page), key=Fernet.generate_key())
    origin = "chrome-extension://" + "a" * 32
    with TestClient(app, base_url="http://127.0.0.1:1455") as client:
        paired = client.post("/pair", headers={"Origin": origin}, json={"code": app.state.pair_code, "extension_id": "a" * 32})
        headers = {"Origin": origin, "X-Composer-Token": paired.json()["pair_token"]}
        client.put("/profile", headers=headers, json={"name": "Alex", "facts": [
            {"id": "match", "text": "Built Python FastAPI services with RabbitMQ.", "confirmed": True},
            {"id": "unreviewed", "text": "Invented Python metric.", "confirmed": False},
        ]})
        body = {"mode": "dm", "model": "offline-demo", "prompt": "Write a referral DM", "tone": "Professional", "job_input": "https://jobs.example.com/role"}
        assert client.post("/generate", json=body, headers={"Origin": origin}).status_code == 401
        events = [json.loads(line) for line in client.post("/generate", json=body, headers=headers).text.splitlines()]
        assert events[0]["message"] == "Reading job…"
        assert events[1]["job"]["company"] == "Example Labs"
        assert [fact["id"] for fact in events[2]["facts"]] == ["match"]
        assert events[-2]["text"].startswith("Hi,") and "Backend Engineer" in events[-2]["text"]
        assert events[-1]["type"] == "done"
