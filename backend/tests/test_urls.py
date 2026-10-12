import pytest

from app.source_providers.url_validation import (
    normalize_instagram_url,
    normalize_linkedin_url,
)


def test_valid_linkedin():
    assert (
        normalize_linkedin_url("https://www.linkedin.com/in/jane-doe")
        == "https://www.linkedin.com/in/jane-doe"
    )


def test_valid_instagram():
    assert (
        normalize_instagram_url("https://www.instagram.com/jane.doe/")
        == "https://www.instagram.com/jane.doe"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/in/jane",
        "http://127.0.0.1/in/jane",
        "https://localhost/in/jane",
        "ftp://linkedin.com/in/jane",
        "https://www.linkedin.com/company/acme",
    ],
)
def test_invalid_linkedin(url: str):
    with pytest.raises(ValueError):
        normalize_linkedin_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://twitter.com/jane",
        "https://169.254.169.254/latest",
        "https://www.instagram.com/",
    ],
)
def test_invalid_instagram(url: str):
    with pytest.raises(ValueError):
        normalize_instagram_url(url)
