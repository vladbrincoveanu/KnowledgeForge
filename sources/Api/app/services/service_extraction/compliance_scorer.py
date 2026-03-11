"""Compliance Scorer - Scores service compliance with best practices."""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceScorer:
    """Scores service compliance across multiple dimensions."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)

    def score(self, domain: str = None, data_class: str = None,
              owner: str = None, tier: str = None, status: str = None,
              bus_factor: int = None) -> tuple[dict[str, Any], float, list[str]]:
        """Calculate compliance score.

        Returns:
            Tuple of (compliance_dict, confidence, factors)
        """
        score = 0
        max_score = 100
        factors = []
        checks = {}

        # CI/CD presence (20 points)
        ci_score, ci_factor = self._check_ci_cd()
        score += ci_score
        checks["ci_cd"] = ci_score
        factors.append(ci_factor)

        # Security scanning (20 points)
        sec_score, sec_factor = self._check_security()
        score += sec_score
        checks["security"] = sec_score
        factors.append(sec_factor)

        # Documentation (15 points)
        doc_score, doc_factor = self._check_documentation()
        score += doc_score
        checks["documentation"] = doc_score
        factors.append(doc_factor)

        # Testing (15 points)
        test_score, test_factor = self._check_testing()
        score += test_score
        checks["testing"] = test_score
        factors.append(test_factor)

        # Monitoring (10 points)
        mon_score, mon_factor = self._check_monitoring()
        score += mon_score
        checks["monitoring"] = mon_score
        factors.append(mon_factor)

        # Containerization (10 points)
        cont_score, cont_factor = self._check_containerization()
        score += cont_score
        checks["containerization"] = cont_score
        factors.append(cont_factor)

        # Infrastructure as Code (10 points)
        iac_score, iac_factor = self._check_iac()
        score += iac_score
        checks["infrastructure_as_code"] = iac_score
        factors.append(iac_factor)

        # Calculate confidence (0-1)
        num_checks = len([v for v in checks.values() if v > 0])
        confidence = min(num_checks / 7.0, 1.0)

        # Determine tier
        tier = "High" if score >= 70 else "Medium" if score >= 40 else "Low"

        compliance_dict = {
            "score": score,
            "tier": tier,
            "checks": checks,
        }

        return compliance_dict, confidence, factors

    def _check_ci_cd(self) -> tuple[int, str]:
        """Check for CI/CD configuration."""
        ci_files = [
            ".github/workflows",
            ".gitlab-ci.yml",
            "Jenkinsfile",
            "azure-pipelines.yml",
            ".circleci/config.yml",
            "bitbucket-pipelines.yml",
        ]

        for ci in ci_files:
            if (self.repo_path / ci).exists():
                return 20, "CI/CD pipeline configured"

        # Check for makefile with test target
        makefile = self.repo_path / "Makefile"
        if makefile.exists():
            content = makefile.read_text(errors="ignore")
            if "test" in content:
                return 10, "Makefile with test target"

        return 0, "No CI/CD detected"

    def _check_security(self) -> tuple[int, str]:
        """Check for security practices."""
        # Check for security files
        sec_files = [
            ".snyk",
            "security.txt",
            ".bandit",
            "sonarqube",
            "trivy",
        ]

        for sec in sec_files:
            if (self.repo_path / sec).exists():
                return 20, "Security scanning configured"

        # Check for dependabot
        if (self.repo_path / ".github" / "dependabot.yml").exists():
            return 15, "Dependency scanning (dependabot)"

        return 0, "No security scanning detected"

    def _check_documentation(self) -> tuple[int, str]:
        """Check for documentation."""
        doc_files = ["README.md", "docs"]

        for df in doc_files:
            path = self.repo_path / df
            if path.exists():
                if path.is_file():
                    return 15, "README present"
                elif path.is_dir():
                    return 10, "docs directory present"

        return 0, "No documentation detected"

    def _check_testing(self) -> tuple[int, str]:
        """Check for tests."""
        test_dirs = ["tests", "test", "__tests__", "specs"]

        for td in test_dirs:
            if (self.repo_path / td).exists():
                return 15, "Test directory present"

        # Check for pytest config
        if (self.repo_path / "pytest.ini").exists() or (self.repo_path / "pyproject.toml").exists():
            return 10, "Test configuration present"

        return 0, "No tests detected"

    def _check_monitoring(self) -> tuple[int, str]:
        """Check for monitoring configuration."""
        # Check for monitoring configs
        monitor_files = [
            "prometheus.yml",
            "grafana",
            "datadog",
            "newrelic",
            "monitoring",
        ]

        for mf in monitor_files:
            if (self.repo_path / mf).exists():
                return 10, "Monitoring configuration present"

        return 0, "No monitoring detected"

    def _check_containerization(self) -> tuple[int, str]:
        """Check for containerization."""
        if (self.repo_path / "Dockerfile").exists():
            return 10, "Dockerfile present"

        return 0, "No containerization detected"

    def _check_iac(self) -> tuple[int, str]:
        """Check for Infrastructure as Code."""
        iac_files = ["terraform", "ansible", "cloudformation", "/pulumi", "/helm"]

        for iac in iac_files:
            if list(self.repo_path.rglob(f"*{iac}*")):
                return 10, "Infrastructure as Code present"

        return 0, "No IaC detected"
