"""Reads a public Instagram profile from its URL.

Instagram pre-renders public profiles for search crawlers; that page embeds the
bio and the latest post captions as JSON. Private profiles are rejected.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.source_providers.base import SourceProvider, Strategy
from app.source_providers.fetch import (
    BROWSER_UA,
    CRAWLER_UA,
    ScrapeError,
    http_get,
    json_scripts,
    meta_content,
    one_line,
    run_apify_actor,
    walk_json,
)
from app.source_providers.url_validation import normalize_instagram_url

IG_WEB_APP_ID = "936619743392459"
_MAX_POSTS = 12
_PRIVATE = "this Instagram profile is private — only public profiles can be read"
_MISSING = "no Instagram profile exists at this URL"


def _username(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _count(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return ""


def build_profile_text(
    url: str,
    *,
    full_name: str,
    username: str,
    biography: str = "",
    category: str = "",
    external_url: str = "",
    followers: Any = None,
    following: Any = None,
    post_count: Any = None,
    verified: bool = False,
    posts: list[dict[str, str]] | None = None,
) -> str:
    lines = [f"[Instagram public profile — {url}]"]
    if full_name:
        lines.append(f"Name: {one_line(full_name, 120)}")
    lines.append(f"Username: @{username}")
    if biography:
        lines.append(f"Bio: {one_line(biography, 600)}")
    if category:
        lines.append(f"Category: {one_line(category, 120)}")
    if external_url:
        lines.append(f"Link in bio: {one_line(external_url, 200)}")
    stats = [
        f"{label}: {_count(value)}"
        for label, value in (
            ("Followers", followers),
            ("Following", following),
            ("Posts", post_count),
        )
        if _count(value)
    ]
    if verified:
        stats.append("Verified account")
    if stats:
        lines.append(" · ".join(stats))
    kept = [p for p in (posts or []) if p.get("caption") or p.get("alt")][:_MAX_POSTS]
    if kept:
        lines.append("Recent Instagram posts (newest first):")
        for i, post in enumerate(kept, start=1):
            where = f"[at {one_line(post['location'], 80)}] " if post.get("location") else ""
            caption = one_line(post.get("caption") or "", 700)
            alt = one_line(post.get("alt") or "", 240)
            body = caption or f"(no caption) {alt}"
            if caption and alt:
                body = f"{caption} (image: {alt})"
            lines.append(f"{i}. {where}{body}")
    return "\n".join(lines)


def parse_instagram_html(page: str, url: str) -> tuple[str, str]:
    """Parse the crawler-rendered profile page into (name, profile text)."""
    username = _username(url)
    user: dict[str, Any] | None = None
    posts: list[dict[str, str]] = []
    seen: set[str] = set()

    for blob in json_scripts(page, "application/json"):
        for node in walk_json(blob):
            if "biography" in node and "username" in node:
                same = str(node.get("username", "")).lower() == username.lower()
                if user is None or same:
                    user = node
            caption = node.get("caption")
            if isinstance(caption, dict) and isinstance(caption.get("text"), str):
                owner = node.get("user") or node.get("owner") or {}
                owner_name = str(owner.get("username", "")) if isinstance(owner, dict) else ""
                if owner_name and owner_name.lower() != username.lower():
                    continue
                key = str(caption.get("pk") or caption["text"][:80])
                if key in seen:
                    continue
                seen.add(key)
                location = node.get("location")
                posts.append(
                    {
                        "caption": caption["text"],
                        "location": location.get("name", "") if isinstance(location, dict) else "",
                        "alt": str(node.get("accessibility_caption") or ""),
                    }
                )

    if user is None:
        raise ScrapeError(
            "no public profile data on the page — the handle may not exist, "
            "or Instagram is blocking this network",
            status="blocked",
        )
    if user.get("is_private"):
        raise ScrapeError(_PRIVATE, status="private_profile", terminal=True)

    full_name = str(user.get("full_name") or "")
    if not full_name:
        full_name = meta_content(page, "og:title").split(" (@")[0]
    text = build_profile_text(
        url,
        full_name=full_name,
        username=str(user.get("username") or username),
        biography=str(user.get("biography") or ""),
        category=str(user.get("category_name") or user.get("category") or ""),
        external_url=str(user.get("external_url") or ""),
        followers=user.get("follower_count"),
        following=user.get("following_count"),
        post_count=user.get("media_count"),
        verified=bool(user.get("is_verified")),
        posts=posts,
    )
    return one_line(full_name, 120), text


def parse_web_profile_info(payload: dict[str, Any], url: str) -> tuple[str, str]:
    """Parse the ``web_profile_info`` JSON endpoint into (name, profile text)."""
    user = (payload.get("data") or {}).get("user")
    if not isinstance(user, dict):
        raise ScrapeError("endpoint returned no user", status="blocked")
    if user.get("is_private"):
        raise ScrapeError(_PRIVATE, status="private_profile", terminal=True)

    posts: list[dict[str, str]] = []
    timeline = user.get("edge_owner_to_timeline_media") or {}
    for edge in timeline.get("edges") or []:
        node = edge.get("node") or {}
        captions = (node.get("edge_media_to_caption") or {}).get("edges") or []
        caption = (captions[0].get("node") or {}).get("text", "") if captions else ""
        location = node.get("location")
        posts.append(
            {
                "caption": caption,
                "location": location.get("name", "") if isinstance(location, dict) else "",
                "alt": str(node.get("accessibility_caption") or ""),
            }
        )

    full_name = str(user.get("full_name") or "")
    text = build_profile_text(
        url,
        full_name=full_name,
        username=str(user.get("username") or _username(url)),
        biography=str(user.get("biography") or ""),
        category=str(user.get("category_name") or ""),
        external_url=str(user.get("external_url") or ""),
        followers=(user.get("edge_followed_by") or {}).get("count"),
        following=(user.get("edge_follow") or {}).get("count"),
        post_count=timeline.get("count"),
        verified=bool(user.get("is_verified")),
        posts=posts,
    )
    return one_line(full_name, 120), text


class InstagramSourceProvider(SourceProvider):
    source_type = "instagram"
    label = "Instagram"

    def validate_url(self, url: str) -> str:
        return normalize_instagram_url(url)

    def _crawler_page(self, url: str) -> tuple[str, str]:
        response = http_get(
            url + "/",
            headers={"User-Agent": CRAWLER_UA, "Accept-Language": "en-US,en;q=0.9"},
            allowed_host="instagram.com",
        )
        if response.status_code == 404:
            raise ScrapeError(_MISSING, status="not_found", terminal=True)
        if "/accounts/login" in str(response.url) or response.status_code in {401, 403, 429}:
            raise ScrapeError(
                f"Instagram served a sign-in wall (HTTP {response.status_code})",
                status="blocked",
            )
        if response.status_code >= 400:
            raise ScrapeError(f"HTTP {response.status_code}")
        return parse_instagram_html(response.text, url)

    def _web_profile_info(self, url: str) -> tuple[str, str]:
        username = _username(url)
        response = http_get(
            f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers={
                "User-Agent": BROWSER_UA,
                "x-ig-app-id": IG_WEB_APP_ID,
                "Accept": "*/*",
                "Referer": url + "/",
            },
            allowed_host="instagram.com",
        )
        if response.status_code == 404:
            raise ScrapeError(_MISSING, status="not_found", terminal=True)
        if response.status_code in {401, 403, 429}:
            raise ScrapeError(
                f"Instagram requires sign-in from this network (HTTP {response.status_code})",
                status="blocked",
            )
        if response.status_code >= 400:
            raise ScrapeError(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ScrapeError("endpoint returned non-JSON", status="blocked") from exc
        return parse_web_profile_info(payload, url)

    def _apify(self, url: str) -> tuple[str, str]:
        username = _username(url)
        record = run_apify_actor(
            get_settings().apify_instagram_actor, {"usernames": [username]}
        )[0]
        if record.get("private"):
            raise ScrapeError(_PRIVATE, status="private_profile", terminal=True)
        posts = [
            {
                "caption": str(p.get("caption") or ""),
                "location": str(p.get("locationName") or ""),
                "alt": str(p.get("alt") or ""),
            }
            for p in record.get("latestPosts") or []
            if isinstance(p, dict)
        ]
        full_name = str(record.get("fullName") or "")
        text = build_profile_text(
            url,
            full_name=full_name,
            username=str(record.get("username") or username),
            biography=str(record.get("biography") or ""),
            category=str(record.get("businessCategoryName") or ""),
            external_url=str(record.get("externalUrl") or ""),
            followers=record.get("followersCount"),
            following=record.get("followsCount"),
            post_count=record.get("postsCount"),
            verified=bool(record.get("verified")),
            posts=posts,
        )
        return one_line(full_name, 120), text

    def strategies(self) -> list[tuple[str, Strategy]]:
        out: list[tuple[str, Strategy]] = [
            ("instagram_crawler_rendered_page", self._crawler_page),
            ("instagram_web_profile_info", self._web_profile_info),
        ]
        if get_settings().apify_token:
            out.append(("apify_instagram_profile_scraper", self._apify))
        return out
