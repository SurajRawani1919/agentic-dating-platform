from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.core.config import get_settings
from app.source_providers.fetch import ScrapeError

AcquisitionStatus = Literal[
    "acquired",
    "participant_provided",
    "unsupported_access",
    "private_profile",
    "not_found",
    "blocked",
    "failed",
    "empty",
]

SourceType = Literal["linkedin", "instagram"]


@dataclass
class AcquisitionResult:
    source_type: SourceType
    submitted_url: str
    acquisition_method: str
    acquisition_status: AcquisitionStatus
    permitted_content: str = ""
    verification_notes: str = ""
    display_name: str = ""
    fetched_at: datetime | None = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def ok(self) -> bool:
        return bool(self.permitted_content.strip())


# A strategy reads one profile and returns (display_name, profile_text).
Strategy = Callable[[str], tuple[str, str]]


class SourceProvider(ABC):
    source_type: SourceType
    label: str

    @abstractmethod
    def validate_url(self, url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def strategies(self) -> list[tuple[str, Strategy]]:
        """Ordered (method_name, strategy) pairs, cheapest first."""
        raise NotImplementedError

    def acquire_permitted_content(
        self, url: str, participant_provided_text: str = ""
    ) -> AcquisitionResult:
        """Read the public profile behind ``url``.

        Tries each strategy in order. Pasted text is only a fallback for when the
        platform blocks every automated read.
        """
        normalized = self.validate_url(url)
        settings = get_settings()
        limit = settings.max_profile_text_chars
        manual = (participant_provided_text or "").strip()[:limit]

        attempts: list[str] = []
        status: AcquisitionStatus = "unsupported_access"
        if settings.scraping_enabled:
            for method, strategy in self.strategies():
                try:
                    name, text = strategy(normalized)
                except ScrapeError as exc:
                    attempts.append(f"{method}: {exc}")
                    status = exc.status  # type: ignore[assignment]
                    if exc.terminal:
                        break
                    continue
                text = text.strip()[:limit]
                if not text:
                    attempts.append(f"{method}: profile returned no readable text")
                    status = "empty"
                    continue
                return AcquisitionResult(
                    source_type=self.source_type,
                    submitted_url=normalized,
                    acquisition_method=method,
                    acquisition_status="acquired",
                    permitted_content=text,
                    display_name=name,
                    verification_notes=(
                        f"Read live from the public {self.label} profile via {method}."
                    ),
                )
        else:
            attempts.append("automatic reading is disabled (SCRAPING_ENABLED=false)")

        tried = " Tried — " + "; ".join(attempts) + "." if attempts else ""
        if manual and status not in {"private_profile", "not_found"}:
            return AcquisitionResult(
                source_type=self.source_type,
                submitted_url=normalized,
                acquisition_method="participant_authorized_text",
                acquisition_status="participant_provided",
                permitted_content=manual,
                verification_notes=(
                    f"The public {self.label} profile could not be read automatically, "
                    f"so the pasted profile text was used instead.{tried}"
                ),
            )
        return AcquisitionResult(
            source_type=self.source_type,
            submitted_url=normalized,
            acquisition_method="none",
            acquisition_status=status,
            permitted_content="",
            verification_notes=f"Could not read the {self.label} profile.{tried}",
        )

    def report_acquisition_status(self, result: AcquisitionResult) -> str:
        return result.acquisition_status
