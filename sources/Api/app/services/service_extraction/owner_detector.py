"""Unified owner/team detection with 4-step fallback chain.

Detection order (stops at first match):
  1. CODEOWNERS file  → @org/team-name patterns
  2. git blame        → top committer in last 90 days
  3. CI config        → TEAM/SLACK env vars in GitHub Actions / Jenkinsfile / GitLab CI
  4. UNKNOWN          → explicit sentinel so callers can distinguish "not found"
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Detection source labels (written to service.owner_detection_source)
SOURCE_CODEOWNERS = "CODEOWNERS"
SOURCE_GIT_BLAME = "git_blame"
SOURCE_CI_CONFIG = "ci_config"
SOURCE_UNKNOWN = "UNKNOWN"

# CI files that often carry team/channel metadata
_CI_FILES = [
    ".github/workflows",          # directory – we'll scan *.yml inside
    "Jenkinsfile",
    ".gitlab-ci.yml",
    ".circleci/config.yml",
]

# Env-var / key patterns that indicate team ownership in CI files
_CI_TEAM_PATTERNS = [
    r'TEAM[_\s:=]+["\']?([A-Za-z0-9_\-]+)',
    r'SQUAD[_\s:=]+["\']?([A-Za-z0-9_\-]+)',
    r'OWNER[_\s:=]+["\']?([A-Za-z0-9_\-]+)',
    r'SLACK_CHANNEL[_\s:=]+["\']?#?([A-Za-z0-9_\-]+)',
    r'NOTIFY_TEAM[_\s:=]+["\']?([A-Za-z0-9_\-]+)',
]


class OwnerDetector:
    """4-step fallback chain for detecting service/repo ownership."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.is_git_repo = (self.repo_root / ".git").exists()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def detect(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None,
    ) -> tuple[str, str]:
        """Detect owner and the source that provided it.

        Args:
            service_path: Absolute or repo-relative path to the service directory.
            service_name:  Service name (used as fallback for git blame path).

        Returns:
            (owner, detection_source) where detection_source is one of
            SOURCE_CODEOWNERS / SOURCE_GIT_BLAME / SOURCE_CI_CONFIG / SOURCE_UNKNOWN.
        """
        search_root = self._resolve_search_root(service_path)

        # Step 1 – CODEOWNERS
        owner = self._from_codeowners(search_root)
        if owner:
            logger.info(f"Owner '{owner}' found via CODEOWNERS for {service_name or service_path}")
            return owner, SOURCE_CODEOWNERS

        # Step 2 – git blame (top committer last 90 days)
        owner = self._from_git_blame(service_path, service_name)
        if owner:
            logger.info(f"Owner '{owner}' found via git blame for {service_name or service_path}")
            return owner, SOURCE_GIT_BLAME

        # Step 3 – CI config env vars
        owner = self._from_ci_config(search_root)
        if owner:
            logger.info(f"Owner '{owner}' found via CI config for {service_name or service_path}")
            return owner, SOURCE_CI_CONFIG

        # Step 4 – give up
        logger.info(f"No owner found for {service_name or service_path}, returning UNKNOWN")
        return "UNKNOWN", SOURCE_UNKNOWN

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: CODEOWNERS
    # ─────────────────────────────────────────────────────────────────────────

    def _from_codeowners(self, search_root: Path) -> Optional[str]:
        """Return first @org/team found in CODEOWNERS files."""
        candidate_dirs = [search_root, self.repo_root]
        seen: set[Path] = set()
        for base in candidate_dirs:
            for name in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
                path = (base / name).resolve()
                if path in seen or not path.exists():
                    continue
                seen.add(path)
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    # @org/team pattern (most specific)
                    teams = re.findall(r"@([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)", content)
                    if teams:
                        return teams[0]
                    # fallback: bare @username
                    users = re.findall(r"@([A-Za-z0-9_-]+)", content)
                    if users:
                        return users[0]
                except (OSError, ValueError):
                    pass
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: git blame (top committer)
    # ─────────────────────────────────────────────────────────────────────────

    def _from_git_blame(
        self,
        service_path: Optional[Path],
        service_name: Optional[str],
    ) -> Optional[str]:
        """Return top committer name/email from git log for the service path."""
        if not self.is_git_repo:
            return None

        rel_path = self._to_rel_path(service_path) if service_path else None

        cmd = [
            "git", "log",
            "--since=90 days ago",
            "--format=%an|%ae",
        ]
        if rel_path:
            cmd += ["--", str(rel_path)]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.SubprocessError, OSError):
            return None

        if result.returncode != 0 or not result.stdout.strip():
            # No recent commits on this path – try whole repo as fallback
            if rel_path:
                return self._from_git_blame(None, service_name)
            return None

        # Count name|email pairs, pick most frequent
        from collections import Counter
        entries = [line.strip() for line in result.stdout.splitlines() if "|" in line]
        if not entries:
            return None

        counter: Counter[str] = Counter(entries)
        top_entry, _ = counter.most_common(1)[0]
        name, email = top_entry.split("|", 1)
        return name.strip() if name.strip() else email.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: CI config env vars
    # ─────────────────────────────────────────────────────────────────────────

    def _from_ci_config(self, search_root: Path) -> Optional[str]:
        """Scan CI config files for TEAM/OWNER/SLACK_CHANNEL env var values."""
        bases = [search_root, self.repo_root]
        seen: set[Path] = set()

        for base in bases:
            for ci_entry in _CI_FILES:
                ci_path = base / ci_entry
                if not ci_path.exists():
                    continue

                # If it's a directory (GitHub Actions), scan all .yml files inside
                files_to_scan: list[Path] = []
                if ci_path.is_dir():
                    files_to_scan = list(ci_path.glob("*.yml")) + list(ci_path.glob("*.yaml"))
                else:
                    files_to_scan = [ci_path]

                for fpath in files_to_scan:
                    if fpath in seen:
                        continue
                    seen.add(fpath)
                    owner = self._scan_file_for_team(fpath)
                    if owner:
                        return owner

        return None

    def _scan_file_for_team(self, path: Path) -> Optional[str]:
        """Apply CI team patterns to a file and return the first match."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        for pattern in _CI_TEAM_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip().strip("\"'")
                # Skip obvious placeholders
                if value.lower() in {"your-team", "team-name", "unknown", "none", "null", "todo"}:
                    continue
                if len(value) >= 2:
                    return value
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_search_root(self, service_path: Optional[Path]) -> Path:
        """Return the directory to search for CODEOWNERS / CI files."""
        if not service_path:
            return self.repo_root
        p = Path(service_path)
        if not p.is_absolute():
            p = self.repo_root / p
        if p.is_file():
            p = p.parent
        return p if p.exists() else self.repo_root

    def _to_rel_path(self, service_path: Path) -> Optional[Path]:
        """Convert to repo-relative path for git commands."""
        try:
            p = Path(service_path)
            if p.is_absolute():
                return p.relative_to(self.repo_root)
            return p
        except ValueError:
            return None
