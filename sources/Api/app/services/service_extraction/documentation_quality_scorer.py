"""Documentation quality scorer for services.

Produces a 0-100 score reflecting how well a service is documented:

  6-check rubric (default weights sum to 100):
    1. README depth          25 pts  – meaningful README with sections
    2. OpenAPI/Swagger spec  20 pts  – machine-readable API contract
    3. Inline doc coverage   20 pts  – docstrings / JSDoc in source files
    4. ADR directory         15 pts  – architecture decision records
    5. CHANGELOG             10 pts  – versioned change log
    6. Examples              10 pts  – examples/ or samples/ directory

Thresholds:
  >= 75  → EXCELLENT
  >= 45  → ADEQUATE
  <  45  → POOR
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)

# ── Default weights (must sum to 100) ────────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, int] = {
    "readme":     25,
    "openapi":    20,
    "inline_docs": 20,
    "adrs":       15,
    "changelog":  10,
    "examples":   10,
}

# ── Tier thresholds ───────────────────────────────────────────────────────────
THRESHOLD_EXCELLENT = 75
THRESHOLD_ADEQUATE  = 45

# ── README quality signals ────────────────────────────────────────────────────
README_SECTION_PATTERNS = [
    re.compile(r"##?\s+(installation|install|setup|getting started)", re.I),
    re.compile(r"##?\s+(usage|quick start|quickstart|how to use)", re.I),
    re.compile(r"##?\s+(api|endpoints|reference)", re.I),
    re.compile(r"##?\s+(contributing|contribution)", re.I),
    re.compile(r"##?\s+(configuration|config)", re.I),
    re.compile(r"##?\s+(license)", re.I),
]
README_MIN_CHARS = 300  # at least this many characters to be "meaningful"
README_GOOD_SECTIONS = 3  # need at least this many recognised sections for full credit

# ── Inline doc file extensions and patterns ───────────────────────────────────
_DOCSTRING_EXTENSIONS = {
    ".py": re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', re.MULTILINE),
    ".js": re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE),
    ".ts": re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE),
    ".tsx": re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE),
    ".jsx": re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE),
    ".java": re.compile(r"/\*\*[\s\S]*?\*/", re.MULTILINE),
    ".go": re.compile(r"//\s+\w.*", re.MULTILINE),
    ".rb": re.compile(r"#\s+\w.*", re.MULTILINE),
}
_MIN_SOURCE_FILES = 3   # ignore tiny repos for inline-doc check
_MIN_DOC_RATIO   = 0.3  # 30% of source files must have at least one docstring/JSDoc


@dataclass
class DocCheckResult:
    name: str
    passed: bool
    weight: int
    evidence: str


@dataclass
class DocumentationQualityResult:
    score: int                              # 0-100
    tier: str                               # EXCELLENT / ADEQUATE / POOR
    checks: list[DocCheckResult] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "tier": self.tier,
            "factors": self.factors,
        }


class DocumentationQualityScorer:
    """Compute a documentation quality score for a service."""

    def __init__(self, weights: Optional[dict[str, int]] = None):
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    # ─────────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────────

    def score(self, service_path: Optional[Path]) -> DocumentationQualityResult:
        """Run all checks and return a DocumentationQualityResult."""
        if not service_path or not Path(service_path).exists():
            return DocumentationQualityResult(
                score=0,
                tier="POOR",
                factors=["Service path not found – cannot assess documentation"],
            )

        root = Path(service_path)

        checks: list[DocCheckResult] = [
            self._check_readme(root),
            self._check_openapi(root),
            self._check_inline_docs(root),
            self._check_adrs(root),
            self._check_changelog(root),
            self._check_examples(root),
        ]

        total_weight = sum(self.weights.get(c.name, 0) for c in checks)
        earned = sum(self.weights.get(c.name, 0) for c in checks if c.passed)
        score = round(earned * 100 / total_weight) if total_weight else 0
        tier = self._score_to_tier(score)

        passed_count = sum(1 for c in checks if c.passed)
        factors: list[str] = [
            f"Score: {passed_count}/{len(checks)} checks passed ({score}/100)"
        ]
        for c in checks:
            icon = "✅" if c.passed else "❌"
            factors.append(f"{icon} {c.evidence}")

        return DocumentationQualityResult(
            score=score,
            tier=tier,
            checks=checks,
            factors=factors,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Individual checks
    # ─────────────────────────────────────────────────────────────────────────

    def _check_readme(self, root: Path) -> DocCheckResult:
        readme_files = list(root.glob("README*")) + list(root.glob("readme*"))
        if not readme_files:
            return DocCheckResult("readme", False, self.weights.get("readme", 0), "No README file found")

        try:
            content = readme_files[0].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return DocCheckResult("readme", True, self.weights.get("readme", 0), "README file present (unreadable)")

        if len(content.strip()) < README_MIN_CHARS:
            return DocCheckResult(
                "readme", False, self.weights.get("readme", 0),
                f"README too short ({len(content)} chars, need {README_MIN_CHARS}+)"
            )

        matched_sections = sum(1 for p in README_SECTION_PATTERNS if p.search(content))
        passed = matched_sections >= README_GOOD_SECTIONS
        evidence = (
            f"README has {matched_sections} recognised sections ({len(content)} chars)"
            if passed
            else f"README present but sparse ({matched_sections}/{README_GOOD_SECTIONS} sections, {len(content)} chars)"
        )
        return DocCheckResult("readme", passed, self.weights.get("readme", 0), evidence)

    def _check_openapi(self, root: Path) -> DocCheckResult:
        # Direct file matches
        direct_signals = [
            root / "openapi.json",
            root / "openapi.yaml",
            root / "openapi.yml",
            root / "swagger.json",
            root / "swagger.yaml",
            root / "swagger.yml",
            root / "api" / "openapi.yaml",
            root / "api" / "openapi.json",
            root / "docs" / "openapi.yaml",
            root / "docs" / "swagger.json",
        ]
        if any(p.exists() for p in direct_signals):
            return DocCheckResult("openapi", True, self.weights.get("openapi", 0), "OpenAPI/Swagger spec file found")

        # Check for openapi key in any top-level YAML
        for yaml_file in list(root.glob("*.yaml")) + list(root.glob("*.yml")):
            try:
                first_lines = yaml_file.read_text(encoding="utf-8", errors="ignore")[:500]
                if "openapi:" in first_lines or "swagger:" in first_lines:
                    return DocCheckResult("openapi", True, self.weights.get("openapi", 0), f"OpenAPI spec in {yaml_file.name}")
            except OSError:
                pass

        return DocCheckResult("openapi", False, self.weights.get("openapi", 0), "No OpenAPI/Swagger specification found")

    def _check_inline_docs(self, root: Path) -> DocCheckResult:
        """Check that at least MIN_DOC_RATIO of source files have docstrings/JSDoc."""
        source_files: list[Path] = []
        documented_files = 0

        for ext, pattern in _DOCSTRING_EXTENSIONS.items():
            try:
                files = list(limited_rglob(root, f"*{ext}"))
            except Exception:
                continue

            # Filter out test/vendor directories
            files = [
                f for f in files
                if not any(
                    part in ("node_modules", ".git", "vendor", "dist", "build", "venv", ".venv")
                    for part in f.parts
                )
            ]
            source_files.extend(files)

            for f in files:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if pattern.search(content):
                        documented_files += 1
                except OSError:
                    pass

        if len(source_files) < _MIN_SOURCE_FILES:
            # Tiny repo — give benefit of the doubt
            return DocCheckResult(
                "inline_docs", True, self.weights.get("inline_docs", 0),
                f"Too few source files ({len(source_files)}) to assess inline docs"
            )

        ratio = documented_files / len(source_files)
        passed = ratio >= _MIN_DOC_RATIO
        pct = round(ratio * 100)
        evidence = (
            f"{documented_files}/{len(source_files)} source files documented ({pct}%)"
            if passed
            else f"Low inline doc coverage: {documented_files}/{len(source_files)} files ({pct}%)"
        )
        return DocCheckResult("inline_docs", passed, self.weights.get("inline_docs", 0), evidence)

    def _check_adrs(self, root: Path) -> DocCheckResult:
        adr_signals = [
            root / "docs" / "decisions",
            root / "docs" / "adr",
            root / "docs" / "architecture",
            root / ".adr",
            root / "architecture-decision-records",
            root / "adr",
        ]
        for p in adr_signals:
            if p.is_dir():
                # Must have at least one markdown file to count
                md_files = list(p.glob("*.md")) + list(p.glob("*.rst"))
                if md_files:
                    return DocCheckResult(
                        "adrs", True, self.weights.get("adrs", 0),
                        f"ADR directory found ({p.name}/, {len(md_files)} record(s))"
                    )

        return DocCheckResult("adrs", False, self.weights.get("adrs", 0), "No architecture decision records found")

    def _check_changelog(self, root: Path) -> DocCheckResult:
        changelog_names = [
            "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt",
            "CHANGES.md", "CHANGES.rst", "HISTORY.md", "HISTORY.rst",
            "RELEASES.md", "RELEASE_NOTES.md",
        ]
        for name in changelog_names:
            p = root / name
            if p.exists():
                try:
                    size = p.stat().st_size
                    if size > 100:
                        return DocCheckResult("changelog", True, self.weights.get("changelog", 0), f"{name} present ({size} bytes)")
                except OSError:
                    return DocCheckResult("changelog", True, self.weights.get("changelog", 0), f"{name} present")

        return DocCheckResult("changelog", False, self.weights.get("changelog", 0), "No CHANGELOG file found")

    def _check_examples(self, root: Path) -> DocCheckResult:
        example_signals = [
            root / "examples",
            root / "example",
            root / "samples",
            root / "sample",
            root / "demos",
            root / "demo",
            root / "notebooks",
        ]
        for p in example_signals:
            if p.is_dir():
                contents = list(p.iterdir())
                if contents:
                    return DocCheckResult(
                        "examples", True, self.weights.get("examples", 0),
                        f"Examples directory found ({p.name}/, {len(contents)} item(s))"
                    )

        return DocCheckResult("examples", False, self.weights.get("examples", 0), "No examples directory found")

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_tier(score: int) -> str:
        if score >= THRESHOLD_EXCELLENT:
            return "EXCELLENT"
        if score >= THRESHOLD_ADEQUATE:
            return "ADEQUATE"
        return "POOR"


def score_documentation_quality(service_path: Path) -> int:
    """Convenience function — returns just the 0-100 integer score."""
    return DocumentationQualityScorer().score(service_path).score
