"""Deterministic merge of generated context fields and user overrides."""

from __future__ import annotations

from .canonical_models import CanonicalFieldValue, EffectiveFieldValue, FieldOverride, OverrideStatus


class ContextMergeEngine:
    """Merge generated and overridden values and detect override drift."""

    def merge_field(
        self,
        generated: CanonicalFieldValue | None,
        override: FieldOverride | None,
    ) -> EffectiveFieldValue:
        if override and override.status != OverrideStatus.SUPERSEDED:
            return EffectiveFieldValue(
                generated=generated,
                override=override,
                effective=override.value,
                state="overridden",
            )
        if generated and generated.value not in (None, "", "unknown"):
            return EffectiveFieldValue(
                generated=generated,
                override=override,
                effective=generated.value,
                state="generated",
            )
        return EffectiveFieldValue(
            generated=generated,
            override=override,
            effective="unknown",
            state="missing",
        )

    def update_override_status(
        self,
        override: FieldOverride,
        generated_value: CanonicalFieldValue | None,
        generated_source_rank: int,
    ) -> FieldOverride:
        """Apply stale detection when generated data materially changes."""
        if generated_value is None:
            return override
        if override.value == generated_value.value:
            override.status = OverrideStatus.ACTIVE
            override.needs_review = False
            return override

        rank_improved = generated_source_rank < override.last_generated_source_rank
        confidence_improved = (generated_value.confidence - override.last_generated_confidence) >= 0.2
        if rank_improved or confidence_improved:
            override.status = OverrideStatus.STALE
            override.needs_review = True
        else:
            override.status = OverrideStatus.ACTIVE
            override.needs_review = False

        override.last_generated_value = generated_value.value
        override.last_generated_confidence = generated_value.confidence
        override.last_generated_source_rank = generated_source_rank
        return override

