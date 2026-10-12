"""Profile readers, exercised against page fixtures — never the live sites."""

import json

import pytest

from app.core.config import get_settings
from app.source_providers.base import SourceProvider
from app.source_providers.fetch import ScrapeError, flatten_record, section_texts
from app.source_providers.instagram import (
    InstagramSourceProvider,
    parse_instagram_html,
    parse_web_profile_info,
)
from app.source_providers.linkedin import LinkedInSourceProvider, parse_linkedin_html

LI_URL = "https://www.linkedin.com/in/jane-doe"
IG_URL = "https://www.instagram.com/jane.doe"

LINKEDIN_GRAPH = {
    "@context": "http://schema.org",
    "@graph": [
        {
            "@type": "Person",
            "name": "Jane Doe",
            "url": LI_URL,
            "description": "Climate engineer. Weekend trail runner and amateur baker.",
            "address": {"@type": "PostalAddress", "addressLocality": "Lisbon, Portugal"},
            "jobTitle": ["Staff Engineer"],
            "worksFor": [
                {"@type": "Organization", "name": "Tidewater", "member": {"startDate": 2021}}
            ],
            "alumniOf": [
                {"@type": "EducationalOrganization", "name": "IST Lisbon", "member": {"startDate": 2012, "endDate": 2017}},
                {"@type": "Organization", "name": "Old Employer", "member": {"startDate": 2017, "endDate": 2021}},
            ],
        },
        {
            "@type": "DiscussionForumPosting",
            "author": {"@type": "Person", "name": "Jane Doe", "url": LI_URL},
            "text": "Spent the week mentoring students on tidal energy modelling.",
        },
        {
            "@type": "DiscussionForumPosting",
            "author": {"@type": "Person", "name": "Someone Else", "url": "https://www.linkedin.com/in/other"},
            "text": "This post belongs to a different person and must be ignored.",
        },
    ],
}

# Attribute values contain ">" on the real site, which breaks naive tag-stripping.
LINKEDIN_HTML = f"""
<html><head>
<meta property="og:title" content="Jane Doe - Staff Engineer at Tidewater | LinkedIn">
<script type="application/ld+json">{json.dumps(LINKEDIN_GRAPH)}</script>
</head><body>
<section data-section="experience"><h2>Experience</h2><ul>
  <li><span class="[&>*]:mb-0 text-[18px]">Staff Engineer</span><span class="[&>*]:mb-0">Tidewater</span>
      <span>2021</span><span>- Present</span></li>
</ul></section>
<section data-section="volunteering"><h2>Volunteering</h2><ul>
  <li><span>Trail steward</span><span>Sintra Park</span></li>
</ul></section>
<section data-section="browsemap"><ul><li>Unrelated Stranger</li></ul></section>
</body></html>
"""

INSTAGRAM_PAYLOAD = {
    "require": [
        {
            "data": {
                "xig_user_by_igid_v2": {
                    "full_name": "Jane Doe",
                    "username": "jane.doe",
                    "biography": "Runs up hills, bakes on Sundays 🥐",
                    "follower_count": 1234,
                    "following_count": 321,
                    "is_verified": False,
                    "is_private": False,
                },
                "timeline": [
                    {"caption": {"pk": "1", "text": "Sunrise 21k on the Sintra ridge #trailrunning"}},
                    {"caption": {"pk": "2", "text": "Third attempt at croissants. Getting closer."}},
                    {"caption": {"pk": "1", "text": "Sunrise 21k on the Sintra ridge #trailrunning"}},
                    {
                        "caption": {"pk": "3", "text": "A stranger's post that leaked into the feed"},
                        "user": {"username": "someone_else"},
                    },
                ],
            }
        }
    ]
}


def instagram_html(payload: dict) -> str:
    return (
        '<html><head><meta property="og:title" content="Jane Doe (@jane.doe)"></head><body>'
        f'<script type="application/json" data-sjs>{json.dumps(payload)}</script></body></html>'
    )


def test_linkedin_page_is_parsed_into_profile_text():
    name, text = parse_linkedin_html(LINKEDIN_HTML, LI_URL)
    assert name == "Jane Doe"
    assert "Headline: Staff Engineer at Tidewater" in text
    assert "Location: Lisbon, Portugal" in text
    assert "About: Climate engineer. Weekend trail runner and amateur baker." in text
    assert "Works with: Tidewater (2021–present)" in text
    assert "Studied at: IST Lisbon (2012–2017)" in text
    assert "Previously with: Old Employer (2017–2021)" in text
    assert "- Staff Engineer · Tidewater · 2021 – Present" in text
    assert "- Trail steward · Sintra Park" in text
    assert "mentoring students on tidal energy modelling" in text


def test_linkedin_parser_ignores_other_people_and_markup_noise():
    _, text = parse_linkedin_html(LINKEDIN_HTML, LI_URL)
    assert "different person" not in text
    assert "Unrelated Stranger" not in text
    assert "mb-0" not in text


def test_linkedin_sign_in_wall_is_reported_as_blocked():
    wall = '<html><head><meta property="og:title" content="Sign Up | LinkedIn"></head></html>'
    with pytest.raises(ScrapeError) as err:
        parse_linkedin_html(wall, LI_URL)
    assert err.value.status == "blocked"


def test_section_parser_handles_gt_inside_attributes():
    sections = section_texts(
        '<section data-section="education"><li><a class="[&>*]:x">MIT</a><span>-</span>'
        "<span>2010</span><span>-</span><span>2014</span></li></section>"
    )
    assert sections["education"] == ["MIT – 2010 – 2014"]


def test_instagram_page_is_parsed_into_profile_text():
    name, text = parse_instagram_html(instagram_html(INSTAGRAM_PAYLOAD), IG_URL)
    assert name == "Jane Doe"
    assert "Username: @jane.doe" in text
    assert "Bio: Runs up hills, bakes on Sundays 🥐" in text
    assert "Followers: 1,234" in text
    assert "1. Sunrise 21k on the Sintra ridge #trailrunning" in text
    assert "2. Third attempt at croissants." in text
    # duplicate captions collapse; another account's post is dropped
    assert text.count("Sunrise 21k") == 1
    assert "stranger" not in text


def test_private_instagram_is_rejected():
    payload = json.loads(json.dumps(INSTAGRAM_PAYLOAD))
    payload["require"][0]["data"]["xig_user_by_igid_v2"]["is_private"] = True
    with pytest.raises(ScrapeError) as err:
        parse_instagram_html(instagram_html(payload), IG_URL)
    assert err.value.status == "private_profile"
    assert err.value.terminal is True


def test_instagram_page_without_profile_data_is_blocked():
    with pytest.raises(ScrapeError) as err:
        parse_instagram_html("<html><title>Instagram</title></html>", IG_URL)
    assert err.value.status == "blocked"


def test_web_profile_info_payload_is_parsed():
    payload = {
        "data": {
            "user": {
                "full_name": "Jane Doe",
                "username": "jane.doe",
                "biography": "Runs up hills",
                "category_name": "Engineer",
                "is_private": False,
                "edge_followed_by": {"count": 10},
                "edge_owner_to_timeline_media": {
                    "count": 1,
                    "edges": [
                        {
                            "node": {
                                "edge_media_to_caption": {"edges": [{"node": {"text": "Ridge day"}}]},
                                "location": {"name": "Sintra"},
                                "accessibility_caption": "Photo of a mountain trail",
                            }
                        }
                    ],
                },
            }
        }
    }
    name, text = parse_web_profile_info(payload, IG_URL)
    assert name == "Jane Doe"
    assert "Category: Engineer" in text
    assert "1. [at Sintra] Ridge day (image: Photo of a mountain trail)" in text


def test_flatten_record_keeps_text_and_drops_urls():
    text = flatten_record(
        {"fullName": "Jane", "profilePicUrl": "https://x/y.jpg", "jobs": [{"title": "Engineer"}]}
    )
    assert "fullName: Jane" in text
    assert "jobs.title: Engineer" in text
    assert "y.jpg" not in text


# ---- strategy orchestration -------------------------------------------------


@pytest.fixture()
def scraping_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "scraping_enabled", True)


def _provider(monkeypatch, cls: type[SourceProvider], strategies):
    provider = cls()
    monkeypatch.setattr(provider, "strategies", lambda: strategies)
    return provider


def _fail(status: str, terminal: bool = False):
    def strategy(url: str):
        raise ScrapeError("nope", status=status, terminal=terminal)

    return strategy


def test_first_working_strategy_wins(monkeypatch, scraping_on):
    provider = _provider(
        monkeypatch,
        LinkedInSourceProvider,
        [("blocked_path", _fail("blocked")), ("good_path", lambda url: ("Jane Doe", "Name: Jane Doe"))],
    )
    result = provider.acquire_permitted_content(LI_URL)
    assert result.acquisition_status == "acquired"
    assert result.acquisition_method == "good_path"
    assert result.display_name == "Jane Doe"


def test_pasted_text_is_only_a_fallback(monkeypatch, scraping_on):
    working = _provider(
        monkeypatch, LinkedInSourceProvider, [("good_path", lambda url: ("Jane", "scraped text"))]
    )
    assert working.acquire_permitted_content(LI_URL, "pasted").permitted_content == "scraped text"

    blocked = _provider(monkeypatch, LinkedInSourceProvider, [("blocked_path", _fail("blocked"))])
    result = blocked.acquire_permitted_content(LI_URL, "pasted")
    assert result.acquisition_status == "participant_provided"
    assert result.permitted_content == "pasted"
    assert "blocked_path" in result.verification_notes


def test_blocked_without_fallback_reports_why(monkeypatch, scraping_on):
    provider = _provider(monkeypatch, LinkedInSourceProvider, [("blocked_path", _fail("blocked"))])
    result = provider.acquire_permitted_content(LI_URL)
    assert result.acquisition_status == "blocked"
    assert not result.ok
    assert "blocked_path: nope" in result.verification_notes


def test_private_profile_stops_and_ignores_pasted_text(monkeypatch, scraping_on):
    called: list[str] = []

    def later(url: str):
        called.append(url)
        return "Jane", "text"

    provider = _provider(
        monkeypatch,
        InstagramSourceProvider,
        [("first", _fail("private_profile", terminal=True)), ("second", later)],
    )
    result = provider.acquire_permitted_content(IG_URL, "pasted bio")
    assert result.acquisition_status == "private_profile"
    assert not result.ok
    assert called == []


def test_scraping_disabled_uses_pasted_text():
    result = LinkedInSourceProvider().acquire_permitted_content(LI_URL, "pasted profile")
    assert result.acquisition_status == "participant_provided"
    assert LinkedInSourceProvider().acquire_permitted_content(LI_URL).acquisition_status == (
        "unsupported_access"
    )
