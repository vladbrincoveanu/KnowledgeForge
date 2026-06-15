"""Manager-relevant git signals derived from the cloned repo's history.

These signals fill the activity / ownership fields that the Graphify AST pass
does not provide:

  * recency  — last commit date, days since last commit
  * cadence  — commit count over fixed time windows
  * people   — contributor list, top contributor, bus factor

The functions are deterministic, do not call any LLM, and degrade silently to
an empty result if the path is not a git repo or git is missing.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Time windows we expose as commit_count_<N>d fields.
_WINDOWS_DAYS: tuple[int, ...] = (30, 90)

# Cap how many contributors we keep in the JSON — long-lived repos can have
# thousands of authors and the manager view only needs the top of the list.
_MAX_CONTRIBUTORS_KEPT = 20

# Fraction of total commits the bus_factor must cover.
_BUS_FACTOR_THRESHOLD = 0.5

# Per-command timeout in seconds.
_GIT_TIMEOUT = 30

# Substrings that identify automated / CI accounts (checked on lowercased values).
_BOT_EMAIL_SUBSTRINGS: tuple[str, ...] = (
    "noreply",
    "github-actions",
    "dependabot",
    "bot@",
    ".bot@",
    "actions@github",
    "renovate",
    "snyk-bot",
    "pre-commit-ci",
)
_BOT_NAME_SUBSTRINGS: tuple[str, ...] = (
    "[bot]",
    "-bot",
    "github actions",
    "renovate",
    "dependabot",
    "snyk bot",
    "pre-commit",
)


def _git(repo_path: Path, *args: str) -> str:
    """Run a git command in *repo_path*; return stdout or empty on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("git %s failed in %s: %s", args, repo_path, exc)
        return ""
    if result.returncode != 0:
        logger.debug("git %s nonzero in %s: %s", args, repo_path, result.stderr[:200])
        return ""
    return result.stdout


def _parse_shortlog(text: str) -> list[dict[str, Any]]:
    """Parse `git shortlog -sne` output into a list of contributor dicts."""
    contributors: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: "<count>\t<name> <<email>>" — \t is consistent across git versions.
        try:
            count_str, rest = line.split("\t", 1)
            commits = int(count_str.strip())
        except ValueError:
            continue
        name = rest
        email = ""
        if rest.endswith(">") and "<" in rest:
            cut = rest.rfind("<")
            name = rest[:cut].strip()
            email = rest[cut + 1 : -1].strip()
        contributors.append({"name": name, "email": email, "commits": commits})
    return contributors


def _is_bot(name: str, email: str) -> bool:
    """Return True when the contributor looks like an automated account."""
    name_l = name.lower()
    email_l = email.lower()
    for pat in _BOT_EMAIL_SUBSTRINGS:
        if pat in email_l:
            return True
    for pat in _BOT_NAME_SUBSTRINGS:
        if pat in name_l:
            return True
    return False


def _dedup_by_email(contributors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge contributors that share the same email.

    The same person often appears under several name strings (display name
    vs. corporate name vs. git config name). We group by normalised email and
    sum the commit counts, picking whichever name string had the most commits
    as the canonical display name.
    """
    # email_key -> {canonical_email, total_commits, name -> commits_under_that_name}
    groups: dict[str, dict[str, Any]] = {}

    for c in contributors:
        raw_email = c["email"]
        # Normalise to lowercase; fall back to lowercased name when email is empty
        key = raw_email.lower() if raw_email else c["name"].lower()
        commits = int(c.get("commits", 0))

        if key not in groups:
            groups[key] = {
                "email": raw_email,
                "commits": 0,
                "name_tally": {},
            }
        groups[key]["commits"] += commits
        tally = groups[key]["name_tally"]
        tally[c["name"]] = tally.get(c["name"], 0) + commits

    result: list[dict[str, Any]] = []
    for data in groups.values():
        best_name = max(data["name_tally"], key=lambda n: data["name_tally"][n])
        result.append({
            "name": best_name,
            "email": data["email"],
            "commits": data["commits"],
        })
    return result


def _compute_bus_factor(contributors: list[dict[str, Any]], total: int) -> int:
    """Smallest N contributors whose combined commits cover the threshold."""
    if total <= 0 or not contributors:
        return 0
    running = 0
    for idx, c in enumerate(contributors, start=1):
        running += int(c.get("commits", 0))
        if running >= total * _BUS_FACTOR_THRESHOLD:
            return idx
    return len(contributors)


def collect_git_signals(repo_path: Path) -> dict[str, Any]:
    """Compute manager-relevant git signals for *repo_path*.

    Returns an empty dict when the path is not a git repo so callers can
    safely `dict.update()` with the result.
    """
    if not (repo_path / ".git").exists():
        return {}

    signals: dict[str, Any] = {}

    # Recency
    last_iso = _git(repo_path, "log", "-1", "--format=%cI").strip()
    if last_iso:
        signals["last_commit_date"] = last_iso
        try:
            last_dt = datetime.fromisoformat(last_iso)
            now = datetime.now(timezone.utc)
            signals["days_since_last_commit"] = max(0, (now - last_dt).days)
        except ValueError:
            pass

    # Cadence
    for days in _WINDOWS_DAYS:
        out = _git(repo_path, "log", f"--since={days}.days", "--format=%H")
        signals[f"commit_count_{days}d"] = sum(1 for ln in out.splitlines() if ln.strip())

    # People — deduplicate by email, then remove bots
    raw = _parse_shortlog(_git(repo_path, "shortlog", "-sne", "HEAD"))
    deduped = _dedup_by_email(raw)
    humans = [c for c in deduped if not _is_bot(c["name"], c["email"])]
    humans.sort(key=lambda c: -int(c.get("commits", 0)))

    # contributor_count and total_commits reflect ALL authors (including bots)
    # so managers see the true repo activity level.
    all_sorted = sorted(deduped, key=lambda c: -int(c.get("commits", 0)))
    total_commits = sum(int(c.get("commits", 0)) for c in all_sorted)
    signals["contributor_count"] = len(humans)  # human headcount
    signals["total_commits"] = total_commits

    if humans:
        total_human = sum(int(c.get("commits", 0)) for c in humans)
        top = humans[0]
        signals["top_contributor"] = {
            "name": top["name"],
            "email": top["email"],
            "commits": top["commits"],
        }
        # Share relative to ALL commits (including bots) so the number is honest.
        signals["top_contributor_share"] = (
            round(top["commits"] / total_commits, 3) if total_commits else 0
        )
        signals["bus_factor"] = _compute_bus_factor(humans, total_human)

    signals["contributors"] = humans[:_MAX_CONTRIBUTORS_KEPT]
    return signals
