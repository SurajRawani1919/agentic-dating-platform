from __future__ import annotations

from app.core.config import get_settings
from app.source_providers.base import AcquisitionResult, SourceProvider
from app.source_providers.url_validation import normalize_instagram_url


class InstagramSourceProvider(SourceProvider):
    source_type = "instagram"

    def validate_url(self, url: str) -> str:
        return normalize_instagram_url(url)

    def acquire_permitted_content(
        self, url: str, participant_provided_text: str = ""
    ) -> AcquisitionResult:
        normalized = self.validate_url(url)
        settings = get_settings()
        text = (participant_provided_text or "").strip()
        if len(text) > settings.max_profile_text_chars:
            text = text[: settings.max_profile_text_chars]

        if text:
            return AcquisitionResult(
                source_type="instagram",
                submitted_url=normalized,
                acquisition_method="participant_authorized_text",
                acquisition_status="participant_provided",
                permitted_content=text,
                verification_notes=(
                    "Automatic Instagram retrieval is unavailable. "
                    "Content was supplied by the participant as authorized public profile text. "
                    "URL format was validated; identity is not auto-verified."
                ),
            )

        return AcquisitionResult(
            source_type="instagram",
            submitted_url=normalized,
            acquisition_method="unsupported_official_access",
            acquisition_status="unsupported_access",
            permitted_content="",
            verification_notes=(
                "Instagram does not provide an officially supported public-profile API "
                "for this application. Automated scraping is not used. "
                "Please submit authorized Instagram profile/bio text to continue analysis."
            ),
        )
