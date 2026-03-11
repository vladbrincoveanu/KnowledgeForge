"""Bus Factor Calculator - Measures bus factor (code ownership spread)."""

import logging
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BusFactorResult:
    bus_factor_score: int  # 1-10 scale
    contributor_count: int
    top_contributor_pct: float
    gini_coefficient: float


def _gini(contributions: list[int]) -> float:
    """Calculate Gini coefficient for contribution distribution.

    0 = perfect equality, 1 = perfect inequality
    """
    if not contributions:
        return 0.0

    n = len(contributions)
    if n == 1:
        return 0.0

    sorted_contrib = sorted(contributions)
    total = sum(sorted_contrib)

    if total == 0:
        return 0.0

    # Calculate Gini
    numerator = sum((2 * (i + 1) - n - 1) * sorted_contrib[i] for i in range(n))
    denominator = n * total

    return numerator / denominator if denominator != 0 else 0.0


def calculate_bus_factor(repo_path: Path) -> BusFactorResult:
    """Calculate bus factor score (1-10) based on contributor distribution.

    Uses Gini coefficient to measure code ownership concentration.
    Lower score = more concentrated (risky), Higher = more distributed.

    Args:
        repo_path: Path to the repository

    Returns:
        BusFactorResult with score (1-10) and metrics
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return BusFactorResult(bus_factor_score=1, contributor_count=0, top_contributor_pct=100.0, gini_coefficient=0.0)

    # Get git contributors
    contributors = _get_contributors(repo_path)

    if not contributors:
        return BusFactorResult(bus_factor_score=1, contributor_count=0, top_contributor_pct=100.0, gini_coefficient=0.0)

    contributor_count = len(contributors)
    commit_counts = [c[1] for c in contributors]

    # Calculate Gini coefficient
    gini = _gini(commit_counts)

    # Calculate top contributor percentage
    total_commits = sum(commit_counts)
    top_pct = (commit_counts[0] / total_commits * 100) if total_commits > 0 else 100.0

    # Convert Gini to score (inverse - high Gini = low bus factor)
    # Gini 0 -> score 10, Gini 1 -> score 1
    score = max(1, min(10, int(round(10 * (1 - gini)))))

    return BusFactorResult(
        bus_factor_score=score,
        contributor_count=contributor_count,
        top_contributor_pct=top_pct,
        gini_coefficient=gini
    )


def _get_contributors(repo_path: Path, max_contributors: int = 100) -> list[tuple[str, int]]:
    """Get contributor names and commit counts."""
    try:
        result = subprocess.run(
            ["git", "shortlog", "-sne", "--all"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        contributors = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            # Parse: "  123  John Doe <john@example.com>"
            match = line.strip().split(None, 2)
            if len(match) >= 2:
                try:
                    count = int(match[0])
                    email = match[1].strip()
                    contributors.append((email, count))
                except ValueError:
                    continue

        return sorted(contributors, key=lambda x: x[1], reverse=True)[:max_contributors]

    except Exception as e:
        logger.debug(f"Failed to get contributors: {e}")
        return []
