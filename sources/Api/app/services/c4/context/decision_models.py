"""Shared decision and review models for C4 context extraction."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DecisionMode(str, Enum):
    """How a field value was produced."""

    DETERMINISTIC = "deterministic"
    LLM_ADJUDICATED = "llm_adjudicated"
    HUMAN_REVIEWED = "human_reviewed"


class ReviewStatus(str, Enum):
    """Review state for an extracted field."""

    AUTO_ACCEPTED = "auto_accepted"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class EvidenceItem:
    """A single evidence item supporting an extracted value."""

    type: str
    source: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass
class ExtractionDecision:
    """Shared extraction result payload for context fields."""

    value: str
    confidence: float
    detection_source: str
    decision_mode: DecisionMode
    review_status: ReviewStatus
    evidence: list[EvidenceItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["decision_mode"] = self.decision_mode.value
        data["review_status"] = self.review_status.value
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


@dataclass
class ReviewItem:
    """Review queue item for ambiguous or conflicting extractions."""

    field: str
    candidate_value: str
    confidence: float
    reason: str
    repo_path: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    recommended_action: str = "human_review"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data
