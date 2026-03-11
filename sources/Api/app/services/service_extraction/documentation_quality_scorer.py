"""Documentation Quality Scoring.

Scores documentation quality based on presence and depth of:
- README, CONTRIBUTING, API docs, architecture docs, changelogs
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def score_documentation_quality(repo_path: Path) -> int:
    """Score documentation quality (0-100).

    Args:
        repo_path: Path to the repository

    Returns:
        Score from 0 (no docs) to 100 (excellent docs)
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return 0

    score = 0

    # Check README (up to 40 points)
    score += _check_readme(repo_path)

    # Check API documentation (up to 20 points)
    score += _check_api_docs(repo_path)

    # Check contributing guide (up to 10 points)
    score += _check_contributing(repo_path)

    # Check changelog (up to 10 points)
    score += _check_changelog(repo_path)

    # Check architecture docs (up to 10 points)
    score += _check_architecture_docs(repo_path)

    # Check code of conduct (up to 5 points)
    score += _check_code_of_conduct(repo_path)

    # Check license (up to 5 points)
    score += _check_license(repo_path)

    return min(score, 100)


def _check_readme(repo_path: Path) -> int:
    """Check for README file with content depth."""
    readme_files = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
    ]

    for rf in readme_files:
        readme = repo_path / rf
        if readme.exists() and readme.is_file():
            try:
                content = readme.read_text(encoding="utf-8", errors="ignore")
                content_lower = content.lower()

                # Basic presence: 10 points
                score = 10

                # Has substantial content (>500 chars): +10
                if len(content) > 500:
                    score += 10

                # Has sections: +5 each
                sections = ["install", "usage", "getting started", "api", "configuration", "deployment"]
                for section in sections:
                    if section in content_lower:
                        score += 5

                # Has badges: +5
                if "![build]" in content_lower or "badge" in content_lower:
                    score += 5

                # Has code examples: +5
                if "```" in content or "    " in content.split("usage")[1:] if "usage" in content_lower else False:
                    score += 5

                return min(score, 40)
            except Exception:
                return 10

    return 0


def _check_api_docs(repo_path: Path) -> int:
    """Check for API documentation."""
    score = 0

    # Check for OpenAPI/Swagger specs
    openapi_files = list(repo_path.rglob("openapi*.json")) + list(repo_path.rglob("swagger*.json"))
    if openapi_files:
        score += 10

    # Check for API doc directory
    api_doc_dirs = ["docs/api", "api-docs", "apidocs", "reference"]
    for d in api_doc_dirs:
        if (repo_path / d).exists():
            score += 10
            break

    # Check for generated API docs
    if (repo_path / "docs").exists():
        try:
            for f in (repo_path / "docs").iterdir():
                if f.is_file() and f.suffix in [".md", ".html"]:
                    score += 5
                    if score >= 20:
                        break
        except Exception:
            pass

    return min(score, 20)


def _check_contributing(repo_path: Path) -> int:
    """Check for CONTRIBUTING guide."""
    contributing_files = [
        "CONTRIBUTING.md",
        "CONTRIBUTING.rst",
        "CONTRIBUTING.txt",
        ".github/CONTRIBUTING.md",
    ]

    for cf in contributing_files:
        if (repo_path / cf).exists():
            try:
                content = (repo_path / cf).read_text(encoding="utf-8", errors="ignore")
                if len(content) > 100:
                    return 10
            except Exception:
                return 5

    return 0


def _check_changelog(repo_path: Path) -> int:
    """Check for CHANGELOG."""
    changelog_files = [
        "CHANGELOG.md",
        "CHANGELOG.rst",
        "CHANGELOG.txt",
        "CHANGES.md",
        "HISTORY.md",
    ]

    for clf in changelog_files:
        if (repo_path / clf).exists():
            try:
                content = (repo_path / clf).read_text(encoding="utf-8", errors="ignore")
                if len(content) > 100:
                    return 10
            except Exception:
                return 5

    return 0


def _check_architecture_docs(repo_path: Path) -> int:
    """Check for architecture documentation."""
    arch_doc_paths = [
        "docs/architecture",
        "docs/arch",
        "architecture",
        "ARCHITECTURE.md",
        "DESIGN.md",
    ]

    for adp in arch_doc_paths:
        path = repo_path / adp
        if path.exists():
            if path.is_file():
                return 10
            elif path.is_dir():
                # Check if directory has content
                try:
                    files = list(path.iterdir())
                    if files:
                        return 10
                except Exception:
                    pass

    return 0


def _check_code_of_conduct(repo_path: Path) -> int:
    """Check for code of conduct."""
    coc_files = [
        "CODE_OF_CONDUCT.md",
        "CODE_OF_CONDUCT.rst",
        ".github/CODE_OF_CONDUCT.md",
    ]

    for cocf in coc_files:
        if (repo_path / cocf).exists():
            return 5

    return 0


def _check_license(repo_path: Path) -> int:
    """Check for LICENSE file."""
    license_files = [
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "COPYING",
        "COPYRIGHT",
    ]

    for lf in license_files:
        if (repo_path / lf).exists():
            return 5

    return 0
