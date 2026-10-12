from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


AcquisitionStatus = Literal[
    "acquired",
    "participant_provided",
    "unsupported_access",
    "failed",
    "empty",
]


@dataclass
class AcquisitionResult:
    source_type: Literal["linkedin", "instagram"]
    submitted_url: str
    acquisition_method: str
    acquisition_status: AcquisitionStatus
    permitted_content: str = ""
    verification_notes: str = ""
    fetched_at: datetime | None = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class SourceProvider(ABC):
    source_type: Literal["linkedin", "instagram"]

    @abstractmethod
    def validate_url(self, url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def acquire_permitted_content(
        self, url: str, participant_provided_text: str = ""
    ) -> AcquisitionResult:
        raise NotImplementedError

    def report_acquisition_status(self, result: AcquisitionResult) -> str:
        return result.acquisition_status
