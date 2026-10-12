"""Shared HTTP + parsing helpers for the public-profile readers."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
# Both platforms pre-render public profiles for search crawlers.
CRAWLER_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

APIFY_BASE = "https://api.apify.com/v2"


class ScrapeError(Exception):
    """A single acquisition strategy failed.

    ``status`` maps onto AcquisitionResult.acquisition_status. ``terminal`` means no
    other strategy can succeed (private or missing profile), so stop trying.
    """

    def __init__(self, message: str, *, status: str = "failed", terminal: bool = False):
        super().__init__(message)
        self.status = status
        self.terminal = terminal


def http_get(url: str, *, headers: dict[str, str], allowed_host: str) -> httpx.Response:
    """GET a profile URL, refusing to leave the platform's own host on redirect."""
    settings = get_settings()
    try:
        with httpx.Client(
            follow_redirects=True,
            max_redirects=5,
            timeout=settings.scraper_timeout_seconds,
            proxy=settings.scraper_proxy or None,
        ) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise ScrapeError(f"timed out after {settings.scraper_timeout_seconds}s") from exc
    except httpx.HTTPError as exc:
        raise ScrapeError(f"network error: {exc.__class__.__name__}") from exc

    final_host = (urlparse(str(response.url)).hostname or "").lower()
    if final_host != allowed_host and not final_host.endswith("." + allowed_host):
        raise ScrapeError(f"redirected off-platform to {final_host}", status="blocked")
    return response


def run_apify_actor(actor: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Run an Apify actor synchronously and return its dataset items."""
    settings = get_settings()
    if not settings.apify_token:
        raise ScrapeError("APIFY_TOKEN is not configured", status="unsupported_access")
    url = f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items"
    try:
        with httpx.Client(timeout=180) as client:
            response = client.post(
                url,
                params={"token": settings.apify_token, "timeout": 150},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ScrapeError(f"Apify request failed: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise ScrapeError(f"Apify actor {actor} returned HTTP {response.status_code}")
    try:
        items = response.json()
    except ValueError as exc:
        raise ScrapeError("Apify returned a non-JSON body") from exc
    if not isinstance(items, list) or not items:
        raise ScrapeError(f"Apify actor {actor} returned no items", status="empty")
    return [i for i in items if isinstance(i, dict)]


def clean_text(value: Any) -> str:
    """Collapse whitespace and drop control characters."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"[​‌‍﻿]", "", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def one_line(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", clean_text(value))
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def meta_content(page: str, prop: str) -> str:
    """Read a <meta property|name="prop" content="..."> value."""
    pattern = (
        r'<meta[^>]+(?:property|name)="' + re.escape(prop) + r'"[^>]*content="([^"]*)"'
    )
    match = re.search(pattern, page, flags=re.IGNORECASE)
    if not match:
        pattern = (
            r'<meta[^>]+content="([^"]*)"[^>]*(?:property|name)="' + re.escape(prop) + r'"'
        )
        match = re.search(pattern, page, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def json_scripts(page: str, script_type: str) -> list[Any]:
    """Parse every <script type="..."> JSON blob on the page, skipping broken ones."""
    out: list[Any] = []
    pattern = r'<script[^>]*type="' + re.escape(script_type) + r'"[^>]*>(.*?)</script>'
    for match in re.finditer(pattern, page, flags=re.DOTALL | re.IGNORECASE):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def walk_json(node: Any):
    """Yield every dict nested anywhere inside a JSON value."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


class SectionTextParser(HTMLParser):
    """Extract readable text per ``<section data-section="...">`` block.

    Each ``<li>`` becomes one item; text fragments inside it are joined with " · ".
    A real parser is needed because the markup carries ">" inside attribute values.
    """

    _SKIP = {"script", "style", "svg", "button", "h2", "template", "code"}
    _VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: dict[str, list[str]] = {}
        self._section: str | None = None
        self._depth = 0
        self._skip_depth = 0
        self._parts: list[str] = []

    @staticmethod
    def _join(parts: list[str]) -> str:
        """Join fragments, folding lone dashes into date ranges ("2000 – Present")."""
        out: list[str] = []
        dash = False
        for part in parts:
            if part in {"-", "–", "—"}:
                dash = True
                continue
            if part.startswith(("- ", "– ")):
                part, dash = part[2:], True
            if dash and out:
                out[-1] = f"{out[-1]} – {part}"
            else:
                out.append(part)
            dash = False
        return " · ".join(out)

    def _flush(self) -> None:
        if self._section is None:
            self._parts = []
            return
        item = self._join(self._parts)
        self._parts = []
        if item:
            self.sections[self._section].append(item)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._VOID:
            return
        if self._section is None:
            if tag == "section":
                name = dict(attrs).get("data-section")
                if name:
                    self._section = name
                    self._depth = 1
                    self.sections.setdefault(name, [])
            return
        self._depth += 1
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "li":
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID or self._section is None:
            return
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "li":
            self._flush()
        self._depth -= 1
        if self._depth <= 0:
            self._flush()
            self._section = None
            self._skip_depth = 0

    def handle_data(self, data: str) -> None:
        if self._section is None or self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text and (not self._parts or self._parts[-1] != text):
            self._parts.append(text)


def section_texts(page: str) -> dict[str, list[str]]:
    parser = SectionTextParser()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001 — malformed markup must not abort acquisition
        pass
    return parser.sections


def flatten_record(record: Any, *, max_chars: int = 12000) -> str:
    """Render an arbitrary scraper JSON record as readable ``path: value`` lines.

    Third-party actors disagree on field names, so this keeps every text field
    instead of guessing a schema. URLs, ids and image links are dropped as noise.
    """
    lines: list[str] = []
    noise = re.compile(r"(url|urn|id|image|img|photo|picture|logo|token|tracking)$", re.I)

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if noise.search(str(key)):
                    continue
                visit(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for value in node[:25]:
                visit(value, path)
        elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
            text = one_line(node, 700)
            if text and not text.startswith("http"):
                lines.append(f"{path}: {text}")

    visit(record, "")
    return "\n".join(lines)[:max_chars]
