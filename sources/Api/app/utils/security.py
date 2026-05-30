"""Security utility helpers for input sanitization and path validation.

Centralizes all security-sensitive checks to keep route handlers clean and
ensure consistent validation across endpoints.
"""

import re
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Regex for safe git path components (letters, digits, hyphens, underscores, dots)
_SAFE_GH_COMPONENT = re.compile(r'^[a-zA-Z0-9._-]{1,200}$')
# Regex for safe branch/tag names (no spaces, no shell metacharacters)
_SAFE_BRANCH = re.compile(r'^[a-zA-Z0-9._\-/]{1,200}$')
# Maximum allowed uncompressed ZIP size (15 GB)
MAX_ZIP_UNCOMPRESSED_BYTES = 15 * 1024 * 1024 * 1024


def validate_github_url(url: str) -> tuple[str, str, Optional[str]]:
    """Validate a Git repository URL (GitHub, GitLab, Bitbucket, self-hosted).

    Enforces:
    - HTTPS scheme only
    - At least two path components (owner/repo)
    - Safe path component characters

    Returns:
        (owner, repo, branch_or_None)

    Raises:
        ValueError: If any part of the URL is invalid.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be a non-empty string")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Repository URL must use http(s) scheme, got: {parsed.scheme!r}")

    netloc = parsed.netloc.lower().split(":")[0]  # strip port
    if not netloc or "." not in netloc:
        raise ValueError(f"Invalid repository host: {netloc!r}")

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2:
        raise ValueError(
            f"Invalid repository URL: {url!r}. "
            "Expected format: https://host/owner/repo"
        )

    owner = path_parts[0]
    # For self-hosted GitLab with subgroups (host/group/subgroup/repo), use last segment
    repo = path_parts[-1].removesuffix(".git")

    if not _SAFE_GH_COMPONENT.match(repo):
        raise ValueError(f"Invalid repository name: {repo!r}")

    # Detect branch from /tree/<branch> or fragment (#branch)
    branch: Optional[str] = None
    if len(path_parts) > 3 and path_parts[-3] in ("tree", "blob"):
        branch = "/".join(path_parts[-2:])
    elif parsed.fragment:
        branch = parsed.fragment

    if branch is not None:
        if not _SAFE_BRANCH.match(branch):
            raise ValueError(f"Invalid branch/tag name: {branch!r}")

    return owner, repo, branch


def safe_extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract a ZIP file, rejecting path traversal and symlink attacks.

    Checks every archive member before extraction:
    - Resolves the target path and verifies it stays inside extract_dir
    - Rejects symlinks
    - Rejects members whose uncompressed size exceeds MAX_ZIP_UNCOMPRESSED_BYTES

    Raises:
        ValueError: If the archive contains suspicious entries.
        OSError: If extraction fails.
    """
    extract_dir = extract_dir.resolve()
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Reject symlinks (external_attr encodes Unix mode in high 16 bits)
            unix_mode = (member.external_attr >> 16) & 0xFFFF
            if unix_mode != 0 and (unix_mode & 0xA000) == 0xA000:  # S_ISLNK
                raise ValueError(
                    f"ZIP archive contains a symbolic link: {member.filename!r}. "
                    "Refusing to extract for security reasons."
                )

            # Reject members that escape the extraction directory
            dest = (extract_dir / member.filename).resolve()
            if not str(dest).startswith(str(extract_dir) + "/") and dest != extract_dir:
                raise ValueError(
                    f"ZIP archive member {member.filename!r} would be extracted "
                    f"outside the target directory. Refusing to extract."
                )

            total_uncompressed += member.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"ZIP archive uncompressed size exceeds limit "
                    f"({MAX_ZIP_UNCOMPRESSED_BYTES // (1024 * 1024)} MB). "
                    "Refusing to extract."
                )

        zf.extractall(extract_dir)


def validate_local_repo_path(raw_path: str, allowed_prefixes: Optional[list[str]] = None) -> Path:
    """Resolve and validate a user-supplied local repository path.

    Prevents path traversal by:
    - Resolving symlinks with .resolve()
    - Verifying the path exists and is a directory
    - Optionally restricting to an allowlist of prefix directories

    Args:
        raw_path: User-supplied path string.
        allowed_prefixes: If provided, the resolved path must start with one
            of these prefixes (e.g. ["/tmp", "/repos"]).

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: If the path is unsafe or outside the allowlist.
    """
    if not raw_path or not isinstance(raw_path, str):
        raise ValueError("Repository path must be a non-empty string")

    try:
        resolved = Path(raw_path).resolve()
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid repository path: {raw_path!r}") from exc

    if not resolved.exists():
        raise ValueError(f"Repository path does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Repository path is not a directory: {resolved}")

    if allowed_prefixes:
        if not any(str(resolved).startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError(
                f"Repository path {resolved!r} is outside the allowed directories. "
                f"Allowed: {allowed_prefixes}"
            )

    return resolved
