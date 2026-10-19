"""Read one user-supplied public job page without browser cookies or AI credentials."""
import asyncio
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .errors import AppError

MAX_PAGE = 2_000_000
PASTE_JD = "This job page could not be read. Paste the job description instead."


def job_url(value: str) -> str:
    try:
        if value.startswith("www."):
            value = "https://" + value
        parts = urlsplit(value)
        if (len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value)
                or "\\" in value or parts.scheme != "https" or not parts.hostname
                or parts.username or parts.password or parts.port not in (None, 443)):
            raise ValueError()
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if (host == "linkedin.com" or host.endswith(".linkedin.com")) and not parts.path.startswith("/jobs/view/"):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None:
            if not address.is_global or address.is_multicast:
                raise ValueError()
            host = "[" + host + "]" if address.version == 6 else host
        else:
            if ":" in host or not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host or host.endswith((".local", ".localhost", ".internal")):
                raise ValueError()
        return urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError):
        raise AppError("job_link_invalid", "Use a public HTTPS job link, or paste the JD.") from None


async def public_address(host: str) -> str:
    try:
        records = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(record[4][0] for record in records))
        if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast for address in addresses):
            raise AppError("job_link_invalid", "Use a public job link, or paste the JD.")
        return next((address for address in addresses if ":" not in address), addresses[0])
    except (socket.gaierror, ValueError):
        raise AppError("job_unavailable", PASTE_JD, 422) from None


class PublicJobTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner=None):
        # Separate pools avoid reusing TLS connections across hostnames sharing an IP.
        self.inner = inner or httpx.AsyncHTTPTransport(limits=httpx.Limits(max_connections=4, max_keepalive_connections=0))

    async def handle_async_request(self, request):
        checked = httpx.URL(job_url(str(request.url)))
        address = await public_address(checked.host)
        # Pin the checked DNS answer so a second lookup cannot rebind to localhost.
        pinned = httpx.Request(
            "GET", checked.copy_with(host=address),
            headers={"Host": checked.netloc.decode("ascii"), "User-Agent": "draft-kit/0.9.0 (+public job reader)",
                     "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "identity"},
            extensions={**request.extensions, "sni_hostname": checked.host},
        )
        return await self.inner.handle_async_request(pinned)

    async def aclose(self):
        await self.inner.aclose()


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.lines = []
        self.main_lines = []
        self.title = []
        self.json_scripts = []
        self.json_buffer = None
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property", attrs.get("name", "")).lower()
            self.metadata[key] = attrs.get("content", "")
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.json_buffer = []
        if tag not in {"meta", "br", "img", "input", "hr", "link", "source", "wbr"}:
            self.stack.append((tag, attrs))
        if tag in {"p", "div", "li", "h1", "h2", "h3", "br", "section"}:
            self.lines.append("\n")
            self.main_lines.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self.json_buffer is not None:
            self.json_scripts.append("".join(self.json_buffer))
            self.json_buffer = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in {"p", "div", "li", "h1", "h2", "h3", "section"}:
            self.lines.append("\n")
            self.main_lines.append("\n")

    def handle_data(self, data):
        tags = [tag for tag, _ in self.stack]
        if self.json_buffer is not None:
            self.json_buffer.append(data)
        if "title" in tags:
            self.title.append(data)
        if any(tag in {"script", "style", "noscript", "svg", "head", "nav", "footer", "header"}
               or "hidden" in attrs or attrs.get("aria-hidden") == "true" for tag, attrs in self.stack):
            return
        self.lines.append(data)
        if any(tag in {"main", "article"} or attrs.get("role") == "main" for tag, attrs in self.stack):
            self.main_lines.append(data)


def clean(value: str, limit=14000) -> str:
    parser = Page()
    parser.feed(value)
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.lines).splitlines()]
    return "\n".join(dict.fromkeys(line for line in lines if line))[:limit]


def postings(value):
    if isinstance(value, list):
        for item in value:
            yield from postings(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if "JobPosting" in types:
            yield value
        for key in ("@graph", "mainEntity", "itemListElement", "item"):
            if key in value:
                yield from postings(value[key])


def extract_job(content: str, url: str) -> dict:
    page = Page()
    page.feed(content)
    items = []
    for script in page.json_scripts:
        try:
            items.extend(postings(json.loads(script)))
        except (ValueError, RecursionError):
            continue
    useful = [item for item in items if isinstance(item.get("description"), str) and clean(item["description"])]
    if len(useful) > 1:
        raise AppError("job_ambiguous", "This link lists several roles. Open one job listing, or paste its JD.", 422)
    warnings = []
    if useful:
        job = useful[0]
        title = clean(str(job.get("title", "")), 240)
        organization = job.get("hiringOrganization", {})
        company = clean(str(organization.get("name", "")), 240) if isinstance(organization, dict) else ""
        locations = job.get("jobLocation", [])
        locations = locations if isinstance(locations, list) else [locations]
        location_parts = []
        for entry in locations[:5]:
            address = entry.get("address", {}) if isinstance(entry, dict) else {}
            if isinstance(address, dict):
                location_parts.extend(str(address[key]) for key in ("addressLocality", "addressRegion", "addressCountry") if isinstance(address.get(key), str))
        if job.get("jobLocationType") == "TELECOMMUTE":
            location_parts.insert(0, "Remote")
        location = ", ".join(dict.fromkeys(location_parts))[:300]
        description = clean(job["description"], 16000)
        for key in ("qualifications", "skills", "responsibilities", "experienceRequirements", "employmentType"):
            value = job.get(key)
            if isinstance(value, str):
                description += "\n" + key + ": " + clean(value, 1500)
    else:
        title = clean(page.metadata.get("og:title") or "".join(page.title), 240)
        company, location = "", ""
        body = "".join(page.main_lines).strip() or "".join(page.lines)
        description = clean(body, 16000)
        if len(description) < 100 or not re.search(r"\b(responsibilities|qualifications|requirements|experience|skills|job description|about the role)\b", description, re.I):
            raise AppError("job_unreadable", PASTE_JD, 422)
        if re.search(r"\b(sign in to view|verify you are human|enable javascript|access denied)\b", description, re.I):
            raise AppError("job_unreadable", PASTE_JD, 422)
        warnings.append("Read from page text. Check the role details.")
    if not title or len(description) < 60:
        raise AppError("job_unreadable", PASTE_JD, 422)
    if len(description) > 14000:
        warnings.append("Long JD shortened. Paste relevant details if needed.")
    return {"url": url, "title": title, "company": company, "location": location,
            "description": description[:14000], "warnings": warnings}


class JobReader:
    def __init__(self, client):
        self.client = client

    async def lookup(self, value: str) -> dict:
        url = job_url(value)
        try:
            async with asyncio.timeout(25):
                for _ in range(5):
                    async with self.client.stream("GET", url) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            target = response.headers.get("location")
                            if not target:
                                break
                            url = job_url(urljoin(url, target))
                            continue
                        if response.status_code != 200:
                            raise AppError("job_unavailable", PASTE_JD, 422)
                        if response.headers.get("content-type", "").split(";")[0].lower() not in ("text/html", "application/xhtml+xml"):
                            raise AppError("job_unreadable", "Use a job webpage, or paste the JD.", 422)
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_PAGE:
                                raise AppError("job_too_large", "This job page is too large. Paste the JD instead.", 422)
                        encoding = response.encoding or "utf-8"
                        try:
                            content = data.decode(encoding, errors="replace")
                        except LookupError:
                            content = data.decode("utf-8", errors="replace")
                        return extract_job(content, url)
                raise AppError("job_unavailable", PASTE_JD, 422)
        except (httpx.HTTPError, TimeoutError, OSError):
            raise AppError("job_unavailable", PASTE_JD, 422) from None


def is_job_link(value: str) -> bool:
    return bool(re.match(r"^(?:https?://|www\.)\S+$", value.strip(), re.I))
