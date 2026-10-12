"""Reads a public LinkedIn profile from its URL.

The logged-out profile page carries a schema.org JSON-LD graph (person, roles,
education, recent posts) plus server-rendered sections, so no login is needed.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.source_providers.base import SourceProvider, Strategy
from app.source_providers.fetch import (
    BROWSER_UA,
    CRAWLER_UA,
    ScrapeError,
    flatten_record,
    http_get,
    json_scripts,
    meta_content,
    one_line,
    run_apify_actor,
    section_texts,
)
from app.source_providers.url_validation import normalize_linkedin_url

# data-section name prefix -> heading used in the profile text
_SECTION_LABELS = {
    "experience": "Experience",
    "education": "Education",
    "volunteer": "Volunteering",
    "certification": "Licenses & certifications",
    "licen": "Licenses & certifications",
    "honor": "Honors & awards",
    "award": "Honors & awards",
    "language": "Languages",
    "project": "Projects",
    "publication": "Publications",
    "course": "Courses",
    "organization": "Organizations",
    "skill": "Skills",
    "patent": "Patents",
    "cause": "Causes",
    "interest": "Interests",
}
_NOISE_LINES = ("show more", "show less", "see credential", "see more", "report this")
_MAX_POSTS = 10
_MAX_ARTICLES = 8
_MAX_SECTION_ITEMS = 12


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _span(member: Any) -> str:
    if not isinstance(member, dict):
        return ""
    start, end = member.get("startDate"), member.get("endDate")
    if start and end:
        return f" ({start}–{end})"
    if start:
        return f" ({start}–present)"
    return ""


def _slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].lower()


def parse_linkedin_html(page: str, url: str) -> tuple[str, str]:
    """Turn a public profile page into (name, profile text)."""
    nodes: list[dict[str, Any]] = []
    for blob in json_scripts(page, "application/ld+json"):
        graph = blob.get("@graph") if isinstance(blob, dict) else blob
        nodes.extend(n for n in _as_list(graph or blob) if isinstance(n, dict))

    slug = _slug(url)
    people = [n for n in nodes if n.get("@type") == "Person"]
    person = next(
        (p for p in people if _slug(str(p.get("url") or p.get("sameAs") or "")) == slug),
        people[0] if people else {},
    )

    og_title = meta_content(page, "og:title")
    name = one_line(person.get("name") or og_title.split(" - ")[0].split(" | ")[0], 120)
    if not name or name.lower() in {"linkedin", "sign up", "linkedin login"}:
        raise ScrapeError("page did not contain a public profile", status="blocked")

    headline = ""
    if " - " in og_title:
        headline = og_title.split(" - ", 1)[1].rsplit(" | LinkedIn", 1)[0]

    lines = [f"[LinkedIn public profile — {url}]", f"Name: {name}"]
    if headline:
        lines.append(f"Headline: {one_line(headline, 300)}")
    address = person.get("address") if isinstance(person.get("address"), dict) else {}
    if address.get("addressLocality"):
        lines.append(f"Location: {one_line(address['addressLocality'], 160)}")

    sections = section_texts(page)
    about = person.get("description") or " ".join(sections.get("summary", []))
    if about:
        lines.append(f"About: {one_line(about, 2500)}")

    titles = [one_line(t, 120) for t in _as_list(person.get("jobTitle")) if t]
    if titles:
        lines.append("Roles: " + "; ".join(titles))
    orgs = [
        one_line(o.get("name"), 120) + _span(o.get("member"))
        for o in _as_list(person.get("worksFor"))
        if isinstance(o, dict) and o.get("name")
    ]
    if orgs:
        lines.append("Works with: " + "; ".join(orgs))
    # alumniOf mixes schools with former employers and boards; the @type tells them apart.
    schools, former = [], []
    for org in _as_list(person.get("alumniOf")):
        if not isinstance(org, dict) or not org.get("name"):
            continue
        entry = one_line(org.get("name"), 120) + _span(org.get("member"))
        (schools if org.get("@type") == "EducationalOrganization" else former).append(entry)
    if former:
        lines.append("Previously with: " + "; ".join(former))
    if schools:
        lines.append("Studied at: " + "; ".join(schools))
    for key, label in (("knowsLanguage", "Languages"), ("awards", "Awards")):
        values = []
        for item in _as_list(person.get(key)):
            text = item.get("name") if isinstance(item, dict) else item
            if text:
                values.append(one_line(text, 120))
        if values:
            lines.append(f"{label}: " + "; ".join(values))

    seen_labels: set[str] = set()
    for section_name, items in sections.items():
        label = next(
            (v for k, v in _SECTION_LABELS.items() if section_name.lower().startswith(k)),
            None,
        )
        if not label or label in seen_labels:
            continue
        kept = [
            one_line(i, 400)
            for i in items
            if i and not any(n in i.lower() for n in _NOISE_LINES)
        ][:_MAX_SECTION_ITEMS]
        if kept:
            seen_labels.add(label)
            lines.append(f"{label}:")
            lines.extend(f"- {i}" for i in kept)

    def _by_person(node: dict[str, Any]) -> bool:
        author = node.get("author") if isinstance(node.get("author"), dict) else {}
        return _slug(str(author.get("url") or "")) == slug or author.get("name") == name

    posts = [
        one_line(n.get("text"), 700)
        for n in nodes
        if n.get("@type") == "DiscussionForumPosting" and n.get("text") and _by_person(n)
    ][:_MAX_POSTS]
    if posts:
        lines.append("Recent LinkedIn posts they wrote or shared:")
        lines.extend(f'- "{p}"' for p in posts)
    articles = [
        one_line(n.get("headline"), 200)
        for n in nodes
        if n.get("@type") == "Article" and n.get("headline") and _by_person(n)
    ][:_MAX_ARTICLES]
    if articles:
        lines.append("Articles they published:")
        lines.extend(f'- "{a}"' for a in articles)

    return name, "\n".join(lines)


class LinkedInSourceProvider(SourceProvider):
    source_type = "linkedin"
    label = "LinkedIn"

    def validate_url(self, url: str) -> str:
        return normalize_linkedin_url(url)

    def _public_page(self, user_agent: str) -> Strategy:
        def fetch(url: str) -> tuple[str, str]:
            response = http_get(
                url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                allowed_host="linkedin.com",
            )
            final = str(response.url)
            if response.status_code == 404:
                raise ScrapeError(
                    "no LinkedIn profile exists at this URL",
                    status="not_found",
                    terminal=True,
                )
            if response.status_code in {403, 429, 999} or any(
                marker in final for marker in ("/authwall", "/login", "/checkpoint", "/signup")
            ):
                # LinkedIn answers 999 for missing, non-public and rate-limited profiles alike.
                raise ScrapeError(
                    f"LinkedIn refused the request (HTTP {response.status_code}) — the profile "
                    "may not exist, may not be public, or this network is rate-limited",
                    status="blocked",
                )
            if response.status_code >= 400:
                raise ScrapeError(f"HTTP {response.status_code}")
            return parse_linkedin_html(response.text, url)

        return fetch

    def _apify(self, url: str) -> tuple[str, str]:
        settings = get_settings()
        items = run_apify_actor(
            settings.apify_linkedin_actor,
            {settings.apify_linkedin_input_key: [url]},
        )
        record = items[0]
        name = one_line(
            record.get("fullName")
            or record.get("name")
            or " ".join(
                str(record.get(k) or "") for k in ("firstName", "lastName")
            ).strip(),
            120,
        )
        body = flatten_record(record, max_chars=settings.max_profile_text_chars)
        if not body:
            raise ScrapeError("Apify returned an empty profile", status="empty")
        return name, f"[LinkedIn public profile — {url}]\n{body}"

    def strategies(self) -> list[tuple[str, Strategy]]:
        out: list[tuple[str, Strategy]] = [
            ("linkedin_public_page", self._public_page(BROWSER_UA)),
            ("linkedin_public_page_crawler_render", self._public_page(CRAWLER_UA)),
        ]
        if get_settings().apify_token:
            out.append(("apify_linkedin_actor", self._apify))
        return out
