"""URL validation and SSRF protections for profile source URLs."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

LINKEDIN_RE = re.compile(
    r"^https://(www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?$",
    re.IGNORECASE,
)
INSTAGRAM_RE = re.compile(
    r"^https://(www\.)?instagram\.com/[A-Za-z0-9._]+/?$",
    re.IGNORECASE,
)

BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
}


def _reject_ssrf(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL must include a hostname")
    if host in BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Internal or local network URLs are not allowed")
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("Private or reserved IP addresses are not allowed")
    except ValueError as exc:
        if "Private or reserved" in str(exc) or "Internal or local" in str(exc):
            raise
        # hostname is not an IP literal — OK
        pass


def normalize_linkedin_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.startswith("http://"):
        cleaned = "https://" + cleaned[len("http://") :]
    if cleaned.startswith("linkedin.com/"):
        cleaned = "https://www." + cleaned
    if cleaned.startswith("www.linkedin.com/"):
        cleaned = "https://" + cleaned
    _reject_ssrf(cleaned)
    if not LINKEDIN_RE.match(cleaned + "/" if not cleaned.endswith("/") else cleaned):
        # Allow without trailing slash via regex that already has optional slash
        if not LINKEDIN_RE.match(cleaned):
            raise ValueError(
                "LinkedIn URL must look like https://www.linkedin.com/in/username"
            )
    # Normalize host
    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/")
    return f"https://www.linkedin.com{path}"


def normalize_instagram_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.startswith("http://"):
        cleaned = "https://" + cleaned[len("http://") :]
    if cleaned.startswith("instagram.com/"):
        cleaned = "https://www." + cleaned
    if cleaned.startswith("www.instagram.com/"):
        cleaned = "https://" + cleaned
    _reject_ssrf(cleaned)
    if not INSTAGRAM_RE.match(cleaned):
        raise ValueError(
            "Instagram URL must look like https://www.instagram.com/username"
        )
    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/")
    return f"https://www.instagram.com{path}"
