"""Field precedence and deterministic conflict resolution for canonical context."""

from __future__ import annotations

from .canonical_models import CanonicalFieldValue, FieldCandidate, FieldProvenance


SOURCE_RANKS_BY_FIELD: dict[str, list[str]] = {
    "owner": ["service_universe", "codeowners", "repo_metadata", "commit_history", "heuristic"],
    "lifecycle": ["service_universe", "repo_metadata", "heuristic"],
    "domain": ["service_universe", "repo_metadata", "heuristic"],
    "tier": ["service_universe", "repo_metadata", "heuristic"],
    "data_class": ["compliance_artifact", "service_universe", "repo_metadata", "heuristic"],
    "compliance_flags": ["compliance_artifact", "service_universe", "repo_metadata", "heuristic"],
    "experts": ["service_universe", "repo_metadata", "heuristic"],
}


class FieldPrecedenceResolver:
    """Resolve candidate conflicts with deterministic precedence rules."""

    def __init__(self, unknown_confidence_threshold: float = 0.5):
        self.unknown_confidence_threshold = unknown_confidence_threshold

    def source_rank(self, field_name: str, source_type: str) -> int:
        ranking = SOURCE_RANKS_BY_FIELD.get(field_name, [])
        try:
            return ranking.index(source_type)
        except ValueError:
            return len(ranking) + 100

    def resolve(self, field_name: str, candidates: list[FieldCandidate]) -> CanonicalFieldValue:
        """Resolve a field from candidates or emit explicit unknown state."""
        if not candidates:
            return CanonicalFieldValue(
                value="unknown",
                confidence=0.0,
                provenance=[],
                contested=False,
            )

        sorted_candidates = sorted(
            candidates,
            key=lambda candidate: (
                self.source_rank(field_name, candidate.source_type),
                -candidate.confidence,
                -candidate.last_seen.timestamp(),
                candidate.source_type,
                str(candidate.value),
            ),
        )
        winner = sorted_candidates[0]
        second = sorted_candidates[1] if len(sorted_candidates) > 1 else None
        contested = False
        if second and self.source_rank(field_name, winner.source_type) == self.source_rank(field_name, second.source_type):
            if abs(winner.confidence - second.confidence) <= 0.1 and winner.value != second.value:
                contested = True

        if winner.confidence < self.unknown_confidence_threshold:
            return CanonicalFieldValue(
                value="unknown",
                confidence=winner.confidence,
                provenance=[
                    FieldProvenance(
                        source_type=winner.source_type,
                        source_path=winner.source_path,
                        source_hash=winner.source_hash,
                        artifact_version=winner.artifact_version,
                        extraction_rule=winner.extraction_rule,
                        confidence=winner.confidence,
                        last_seen=winner.last_seen,
                    )
                ],
                contested=contested,
            )

        return CanonicalFieldValue(
            value=winner.value,
            confidence=winner.confidence,
            provenance=[
                FieldProvenance(
                    source_type=winner.source_type,
                    source_path=winner.source_path,
                    source_hash=winner.source_hash,
                    artifact_version=winner.artifact_version,
                    extraction_rule=winner.extraction_rule,
                    confidence=winner.confidence,
                    last_seen=winner.last_seen,
                )
            ],
            contested=contested,
        )

