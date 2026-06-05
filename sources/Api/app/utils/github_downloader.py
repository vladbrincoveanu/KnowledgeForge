"""Minimal GitHub repository downloader for C4 extraction."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


_GIT_URL_PATTERN = re.compile(
    r'^https?://[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._~:@%-]+){2,}(?:\.git)?/?$'
)


class GitHubDownloader:
    """Download Git repositories (GitHub, GitLab, Bitbucket, self-hosted) for analysis."""

    @staticmethod
    def is_github_url(url: str) -> bool:
        """Return True for any HTTPS Git repository URL."""
        return bool(_GIT_URL_PATTERN.match(url.strip()))

    @staticmethod
    def _repo_name_from_url(url: str) -> str:
        """Extract the repository name (last path component) from a Git URL."""
        path = url.rstrip("/").split("?")[0].split("#")[0]
        name = path.rsplit("/", 1)[-1].removesuffix(".git")
        return name or "repo"

    @staticmethod
    def _inject_token(url: str, token: Optional[str] = None) -> str:
        """Inject an auth token into the clone URL.

        Credential format varies by host:
        - GitHub:    https://TOKEN@github.com/...         (token alone as username)
        - GitLab:    https://oauth2:TOKEN@gitlab.host/... (PAT requires oauth2 prefix)
        - Bitbucket: https://USER:APP_PASSWORD@...        (pass token as-is; user supplies user:pass)
        - Other:     https://oauth2:TOKEN@host/...        (safe default for self-hosted git)

        Precedence: explicit token > host-specific env var (GITHUB_TOKEN /
        GITLAB_TOKEN / BITBUCKET_TOKEN) > GIT_TOKEN generic fallback.
        """
        parsed = re.match(r'^(https?://)(.+)', url)
        if not parsed:
            return url
        scheme, rest = parsed.group(1), parsed.group(2)
        host = rest.split("/")[0].lower()

        if not token:
            if "github.com" in host:
                token = os.getenv("GITHUB_TOKEN")
            elif "gitlab" in host:
                token = os.getenv("GITLAB_TOKEN")
            elif "bitbucket.org" in host:
                token = os.getenv("BITBUCKET_TOKEN")
            token = token or os.getenv("GIT_TOKEN")

        if not token:
            return url

        # Choose the right credential format for the host.
        # If the token already contains a colon it's already user:secret — pass through.
        if ":" in token:
            credentials = token
        elif "github.com" in host:
            credentials = token          # GitHub accepts bare token as username
        else:
            credentials = f"oauth2:{token}"  # GitLab / self-hosted require oauth2 prefix

        return f"{scheme}{credentials}@{rest}"

    @staticmethod
    def download_repository(
        github_url: str,
        output_dir: Path,
        use_git: bool = True,
        full_history: bool = True,
        token: Optional[str] = None,
    ) -> Path:
        """Clone a Git repository.

        Args:
            github_url: HTTPS URL of the repository (GitHub, GitLab, Bitbucket, etc.)
            output_dir: Directory to save the repository
            use_git: Use git clone (always True; archive path kept for compat)
            full_history: Clone with full history (default) or shallow (--depth 1)
            token: Optional personal access token for private repositories.
                   Falls back to host-specific env vars (GITHUB_TOKEN, GITLAB_TOKEN,
                   BITBUCKET_TOKEN) then GIT_TOKEN.

        Returns:
            Path to the cloned repository
        """
        logger.info(f"Downloading repository from {github_url}")

        repo = GitHubDownloader._repo_name_from_url(github_url)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        repo_path = output_dir / repo

        clone_url = GitHubDownloader._inject_token(github_url, token=token)
        if not clone_url.endswith(".git"):
            clone_url = clone_url.rstrip("/") + ".git"

        git_cmd = ["git", "clone"]
        if not full_history:
            git_cmd.extend(["--depth", "1"])
        git_cmd.extend([clone_url, str(repo_path)])

        logger.info(f"Running: git clone {'--depth 1 ' if not full_history else ''}{github_url}")
        try:
            subprocess.run(git_cmd, check=True, capture_output=True, text=True, timeout=300)
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e.stderr}")
            raise RuntimeError(f"Failed to clone repository: {e.stderr}")

        logger.info(f"Repository cloned successfully to {repo_path}")
        return repo_path
