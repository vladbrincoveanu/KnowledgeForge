"""Bus Factor calculator for context-level service health scoring.

Computes a composite Bus Factor score (1-10) from git commit history:
    score = active_experts × (1 − gini_coefficient)

- active_experts: contributors with ≥ 3 commits in the last 90 days
- gini_coefficient: concentration of commits across contributors (0 = even,
  1 = one person did everything)

Scale interpretation:
  1   → maximum risk (0 or 1 active expert, highly concentrated)
  5   → moderate risk (2-3 active experts, some concentration)
  8-10 → low risk (4+ active experts, commits well distributed)
"""

import logging
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MIN_COMMITS_FOR_EXPERT = 3
_LOOKBACK_DAYS = 90


@dataclass
class BusFactorResult:
    """Result of bus factor calculation."""

    bus_factor_score: int
    """Composite score 1-10. Higher = lower bus risk."""

    active_experts: int
    """Raw count of contributors with ≥ 3 commits in the last 90 days."""

    gini_coefficient: float
    """Gini coefficient of commit distribution (0 = perfectly even, 1 = one person)."""

    total_contributors_90d: int
    """Total unique contributors in the last 90 days."""

    total_commits_90d: int
    """Total commits in the last 90 days."""


def _gini(values: list[int]) -> float:
    """Compute the Gini coefficient for a list of non-negative integers.

    Uses the efficient sorted-array formula:
        G = (2 * sum(rank * x[rank]) / (n * total)) - (n + 1) / n

    Returns 0.0 for empty or all-zero input (no concentration).
    """
    if not values or sum(values) == 0:
        return 0.0

    n = len(values)
    total = sum(values)
    sorted_vals = sorted(values)

    weighted_sum = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def calculate_bus_factor(
    repo_root: Path,
    service_path: Optional[Path] = None,
    lookback_days: int = _LOOKBACK_DAYS,
    min_commits: int = _MIN_COMMITS_FOR_EXPERT,
) -> BusFactorResult:
    """Compute the Bus Factor score for a service.

    Args:
        repo_root: Root of the git repository.
        service_path: Optional path to restrict the analysis to a subdirectory.
        lookback_days: How far back to look in git history (default 90 days).
        min_commits: Minimum commits for a contributor to be counted as an expert.

    Returns:
        BusFactorResult with score (1-10) and supporting metrics.
        Returns score=1 (max risk) when git history is unavailable.
    """
    repo_root = Path(repo_root).resolve()

    if not (repo_root / ".git").exists():
        logger.debug("Not a git repository — returning default bus factor 1")
        return BusFactorResult(
            bus_factor_score=1,
            active_experts=0,
            gini_coefficient=0.0,
            total_contributors_90d=0,
            total_commits_90d=0,
        )

    try:
        cmd = [
            "git", "log",
            f"--since={lookback_days} days ago",
            "--format=%ae",
        ]
        if service_path:
            try:
                rel_path = service_path.resolve().relative_to(repo_root)
                cmd += ["--", str(rel_path)]
            except ValueError:
                pass  # service_path not inside repo_root — ignore filter

        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return BusFactorResult(
                bus_factor_score=1,
                active_experts=0,
                gini_coefficient=0.0,
                total_contributors_90d=0,
                total_commits_90d=0,
            )

        emails = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        counts = Counter(emails)

        total_contributors = len(counts)
        total_commits = len(emails)
        active_experts = sum(1 for c in counts.values() if c >= min_commits)
        gini = _gini(list(counts.values()))

        # Raw composite: active_experts × (1 − gini)
        # Scale to 1-10:
        #   0   experts or gini≈1  → 1   (max risk)
        #   5+  experts, gini≈0   → 10  (min risk)
        # Formula: clamp(round(raw * 2 + 1), 1, 10)
        raw = active_experts * (1.0 - gini)
        score = min(10, max(1, round(raw * 2 + 1)))

        logger.debug(
            "Bus factor for %s: score=%d, experts=%d, gini=%.2f, total=%d",
            service_path or repo_root,
            score,
            active_experts,
            gini,
            total_contributors,
        )

        return BusFactorResult(
            bus_factor_score=score,
            active_experts=active_experts,
            gini_coefficient=round(gini, 3),
            total_contributors_90d=total_contributors,
            total_commits_90d=total_commits,
        )

    except subprocess.TimeoutExpired:
        logger.warning("git log timed out computing bus factor")
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Failed to compute bus factor: %s", exc)

    return BusFactorResult(
        bus_factor_score=1,
        active_experts=0,
        gini_coefficient=0.0,
        total_contributors_90d=0,
        total_commits_90d=0,
    )
