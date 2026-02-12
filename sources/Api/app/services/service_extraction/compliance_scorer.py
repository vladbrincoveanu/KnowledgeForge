"""Weighted compliance scorer for service architectural health.

Replaces the two separate compliance implementations with a single
configurable scorer that produces:
  - compliance_score: int 0-100
  - compliance tier: "COMPLIANT" | "AT_RISK" | "NON_COMPLIANT" | "UNKNOWN"
  - compliance_factors: list[str] – per-check evidence

7-check rubric (default weights sum to 100):
  1. CI/CD configured        20 pts
  2. Tests present           20 pts
  3. Security scanning       15 pts
  4. No secrets committed    15 pts
  5. README documentation    10 pts
  6. Dependency management   10 pts
  7. Repo structure          10 pts

Thresholds (configurable):
  >= 75  → COMPLIANT
  >= 45  → AT_RISK
  <  45  → NON_COMPLIANT

Extra risk-override rules (independent of score):
  - Sensitive data (PII/CC/Secret) + no owner → force NON_COMPLIANT
  - Sensitive data + ARCHIVED status          → force AT_RISK (floor)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)

# ── Default weights (must sum to 100) ────────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, int] = {
    "cicd":         20,
    "tests":        20,
    "security":     15,
    "no_secrets":   15,
    "readme":       10,
    "dependencies": 10,
    "structure":    10,
}

# ── Tier thresholds ───────────────────────────────────────────────────────────
THRESHOLD_COMPLIANT   = 75
THRESHOLD_AT_RISK     = 45

# ── Sensitive data classes ────────────────────────────────────────────────────
SENSITIVE_DATA_CLASSES = {"PII", "Credit-Card", "Secret"}


@dataclass
class CheckResult:
    name: str
    passed: bool
    weight: int
    evidence: str  # short human-readable description


@dataclass
class ComplianceResult:
    score: int                           # 0-100
    tier: str                            # COMPLIANT / AT_RISK / NON_COMPLIANT / UNKNOWN
    checks: list[CheckResult] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "tier": self.tier,
            "factors": self.factors,
            "confidence": self.confidence,
        }


class ComplianceScorer:
    """Compute a weighted compliance score for a service."""

    def __init__(self, weights: Optional[dict[str, int]] = None):
        """
        Args:
            weights: Override default check weights.  Keys are check names;
                     values are integer points.  Missing keys fall back to defaults.
        """
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    # ─────────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────────

    def score(
        self,
        service_path: Optional[Path],
        data_class: Optional[str] = None,
        owner: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ComplianceResult:
        """
        Run all checks and return a ComplianceResult.

        Args:
            service_path: Root directory of the service to scan.
            data_class:   Sensitivity label (PII, Credit-Card, Secret, Public, …).
            owner:        Owner team/person name (None / "Unassigned" = no owner).
            status:       Lifecycle status string (ARCHIVED, DEPRECATED, …).
        """
        if not service_path or not Path(service_path).exists():
            return ComplianceResult(
                score=0,
                tier="UNKNOWN",
                factors=["Service path not found – cannot assess"],
                confidence=0.0,
            )

        root = Path(service_path)

        checks: list[CheckResult] = [
            self._check_cicd(root),
            self._check_tests(root),
            self._check_security(root),
            self._check_no_secrets(root),
            self._check_readme(root),
            self._check_dependencies(root),
            self._check_structure(root),
        ]

        # Compute weighted score
        total_weight = sum(self.weights.get(c.name, 0) for c in checks)
        earned = sum(
            self.weights.get(c.name, 0) for c in checks if c.passed
        )
        score = round(earned * 100 / total_weight) if total_weight else 0

        # Determine tier from score
        tier = self._score_to_tier(score)

        # Risk override rules (independent of infrastructure checks)
        is_sensitive = (data_class or "") in SENSITIVE_DATA_CLASSES
        no_owner = not owner or owner.strip().lower() in {"", "unassigned", "unknown"}

        if is_sensitive and no_owner:
            tier = "NON_COMPLIANT"
            score = min(score, THRESHOLD_AT_RISK - 1)

        archived = (status or "").upper() in {"ARCHIVED", "DEPRECATED"}
        if is_sensitive and archived and tier == "COMPLIANT":
            tier = "AT_RISK"
            score = min(score, THRESHOLD_COMPLIANT - 1)

        # Build factor strings
        passed_count = sum(1 for c in checks if c.passed)
        factors: list[str] = [
            f"Score: {passed_count}/{len(checks)} checks passed ({score}/100)"
        ]
        for c in checks:
            icon = "✅" if c.passed else "❌"
            factors.append(f"{icon} {c.evidence}")

        # Confidence: improves as we know more about the service
        confidence = 0.5
        if data_class:
            confidence += 0.15
        if owner and not no_owner:
            confidence += 0.15
        if status:
            confidence += 0.2
        confidence = min(1.0, confidence)

        return ComplianceResult(
            score=score,
            tier=tier,
            checks=checks,
            factors=factors,
            confidence=round(confidence, 2),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Individual checks
    # ─────────────────────────────────────────────────────────────────────────

    def _check_cicd(self, root: Path) -> CheckResult:
        cicd_signals = [
            root / ".github" / "workflows",
            root / ".gitlab-ci.yml",
            root / "Jenkinsfile",
            root / ".circleci" / "config.yml",
            root / ".travis.yml",
            root / "bitbucket-pipelines.yml",
            root / "azure-pipelines.yml",
        ]
        passed = any(p.exists() for p in cicd_signals)
        evidence = "CI/CD pipeline configured" if passed else "No CI/CD configuration found"
        return CheckResult("cicd", passed, self.weights.get("cicd", 0), evidence)

    def _check_tests(self, root: Path) -> CheckResult:
        test_signals = [
            root / "tests",
            root / "test",
            root / "__tests__",
            root / "spec",
        ]
        passed = any(p.is_dir() for p in test_signals)
        if not passed:
            # Look for test files anywhere in the tree (quick scan)
            for ext in ("*.test.py", "*_test.py", "*.test.ts", "*.spec.ts", "test_*.py"):
                try:
                    next(limited_rglob(root, ext))
                    passed = True
                    break
                except StopIteration:
                    pass
        evidence = "Tests directory or test files present" if passed else "No tests found"
        return CheckResult("tests", passed, self.weights.get("tests", 0), evidence)

    def _check_security(self, root: Path) -> CheckResult:
        security_signals = [
            root / "SECURITY.md",
            root / ".github" / "SECURITY.md",
            root / ".snyk",
            root / ".trivyignore",
            root / "sonar-project.properties",
        ]
        passed = any(p.exists() for p in security_signals)
        # Also check for security workflow in .github/workflows
        if not passed:
            gha_dir = root / ".github" / "workflows"
            if gha_dir.is_dir():
                for wf in gha_dir.glob("*.yml"):
                    try:
                        content = wf.read_text(encoding="utf-8", errors="ignore").lower()
                        if any(kw in content for kw in ("snyk", "trivy", "sonar", "codeql", "semgrep")):
                            passed = True
                            break
                    except OSError:
                        pass
        evidence = "Security scanning configured" if passed else "No security scanning found"
        return CheckResult("security", passed, self.weights.get("security", 0), evidence)

    def _check_no_secrets(self, root: Path) -> CheckResult:
        # Fail if .env files (not .env.example) are present in the root
        bad = [
            f for f in root.glob(".env*")
            if f.is_file() and "example" not in f.name.lower() and "sample" not in f.name.lower()
        ]
        passed = len(bad) == 0
        if passed:
            # Also check for .gitignore mentioning .env
            gitignore = root / ".gitignore"
            if gitignore.exists():
                try:
                    content = gitignore.read_text(encoding="utf-8", errors="ignore")
                    evidence = "Secrets excluded via .gitignore" if ".env" in content else "No committed .env files"
                except OSError:
                    evidence = "No committed .env files"
            else:
                evidence = "No committed .env files"
        else:
            evidence = f"Potentially committed secrets: {', '.join(f.name for f in bad[:3])}"
        return CheckResult("no_secrets", passed, self.weights.get("no_secrets", 0), evidence)

    def _check_readme(self, root: Path) -> CheckResult:
        readme_files = list(root.glob("README*")) + list(root.glob("readme*"))
        if not readme_files:
            return CheckResult("readme", False, self.weights.get("readme", 0), "No README file found")
        try:
            content = readme_files[0].read_text(encoding="utf-8", errors="ignore")
            passed = len(content.strip()) >= 200  # meaningful README
            evidence = f"README present ({len(content)} chars)" if passed else "README too short (<200 chars)"
        except OSError:
            passed = True  # file exists, can't read
            evidence = "README file present"
        return CheckResult("readme", passed, self.weights.get("readme", 0), evidence)

    def _check_dependencies(self, root: Path) -> CheckResult:
        dep_files = [
            "requirements.txt", "pyproject.toml", "Pipfile",
            "package.json", "pom.xml", "build.gradle",
            "go.mod", "Cargo.toml", "Gemfile",
        ]
        passed = any((root / f).exists() for f in dep_files)
        evidence = "Dependency manifest found" if passed else "No dependency manifest found"
        return CheckResult("dependencies", passed, self.weights.get("dependencies", 0), evidence)

    def _check_structure(self, root: Path) -> CheckResult:
        structure_signals = [
            root / "src",
            root / "app",
            root / "lib",
            root / "services",
            root / "Dockerfile",
            root / "docker-compose.yml",
            root / "docker-compose.yaml",
        ]
        passed = any(p.exists() for p in structure_signals)
        evidence = "Standard project structure detected" if passed else "Non-standard project structure"
        return CheckResult("structure", passed, self.weights.get("structure", 0), evidence)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_tier(score: int) -> str:
        if score >= THRESHOLD_COMPLIANT:
            return "COMPLIANT"
        if score >= THRESHOLD_AT_RISK:
            return "AT_RISK"
        return "NON_COMPLIANT"
