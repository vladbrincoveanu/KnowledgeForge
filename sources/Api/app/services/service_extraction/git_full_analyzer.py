"""Git intelligence analyzer for owners, status, and domain signals."""

import logging
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.models.services import Service, ServiceStatus
from app.services.service_extraction.domain_extractor import DOMAIN_KEYWORDS
from app.services.service_extraction.git_contributor_analyzer import GitContributorAnalyzer
from app.services.service_extraction.git_status_analyzer import GitStatusAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class GitExtendedStats:
    """Extended git statistics for a service."""
    # Branch information
    active_branches: list[str] = field(default_factory=list)
    feature_branches: int = 0
    bugfix_branches: int = 0
    
    # Tag/release information
    tags: list[str] = field(default_factory=list)
    latest_tag: Optional[str] = None
    tag_count: int = 0
    
    # File hotspots (most changed files)
    hotspot_files: list[tuple[str, int]] = field(default_factory=list)
    
    # PR/Issue references from commit messages
    pr_references: list[str] = field(default_factory=list)
    issue_references: list[str] = field(default_factory=list)


class GitFullAnalyzer:
    """Analyze git history for ownership, status, and domain signals."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.is_git_repo = (self.repo_root / ".git").exists()
        self.contributor_analyzer = GitContributorAnalyzer(repo_root)
        self.status_analyzer = GitStatusAnalyzer(repo_root)

    def enrich_service(
        self,
        service: Service,
        service_path: Optional[Path],
        max_contributors: int = 5,
    ) -> None:
        """Populate owner/status/domain fields from git history."""
        if not self.is_git_repo:
            logger.debug(f"Not a git repo, skipping git analysis for {service.name}")
            return

        logger.debug(f"Enriching service {service.name} from git history")
        
        contributor_stats = self.contributor_analyzer.analyze_service_contributors(
            service_path=service_path,
            service_name=service.name,
            max_contributors=max_contributors,
        )

        if contributor_stats:
            top_contributors = contributor_stats.top_contributors
            if top_contributors:
                if not service.owner:
                    top_contributor = top_contributors[0]
                    service.owner = top_contributor.name or top_contributor.email
                service.owner_contributors = [c.email for c in top_contributors]
                service.owner_contributor_stats = [
                    {"email": c.email, "name": c.name, "commit_count": c.commit_count}
                    for c in top_contributors
                ]

            service.contributor_count = contributor_stats.unique_contributors
            service.last_commit_date = contributor_stats.last_commit_date
            service.commit_count_30d = contributor_stats.commits_30d
            service.commit_count_90d = contributor_stats.commits_90d
            service.commit_count_180d = contributor_stats.commits_180d

            # Get extended stats
            extended = self._get_extended_stats(service_path)
            
            service.status_evidence = {
                "total_commits": contributor_stats.total_commits,
                "commits_30d": contributor_stats.commits_30d,
                "commits_90d": contributor_stats.commits_90d,
                "commits_180d": contributor_stats.commits_180d,
                "feature_commits": contributor_stats.feature_commits,
                "bugfix_commits": contributor_stats.bugfix_commits,
                "chore_commits": contributor_stats.chore_commits,
                "last_commit_date": contributor_stats.last_commit_date.isoformat()
                if contributor_stats.last_commit_date
                else None,
                "first_commit_date": contributor_stats.first_commit_date.isoformat()
                if contributor_stats.first_commit_date
                else None,
                "unique_contributors": contributor_stats.unique_contributors,
                "top_contributors": [c.email for c in top_contributors],
                "top_contributor_stats": [
                    {"email": c.email, "name": c.name, "commit_count": c.commit_count}
                    for c in top_contributors
                ],
                "recent_commit_messages": contributor_stats.recent_commit_messages[:10],
                # Extended stats
                "active_branches": extended.active_branches[:5],
                "feature_branches": extended.feature_branches,
                "bugfix_branches": extended.bugfix_branches,
                "tags": extended.tags[:5],
                "latest_tag": extended.latest_tag,
                "tag_count": extended.tag_count,
                "hotspot_files": extended.hotspot_files[:5],
                "pr_references": extended.pr_references[:10],
                "issue_references": extended.issue_references[:10],
            }
            
            logger.debug(f"Git stats for {service.name}: "
                        f"commits_30d={contributor_stats.commits_30d}, "
                        f"branches={extended.feature_branches} feature, "
                        f"tags={extended.tag_count}")

        git_status = self.status_analyzer.analyze_service_status(
            service_path=service_path,
            service_name=service.name,
        )
        if git_status != ServiceStatus.UNKNOWN:
            service.status = git_status
            logger.debug(f"Status from git_status_analyzer: {git_status}")

        if not service.domain:
            domain = self._infer_domain_from_git(service_path, service.name)
            if domain:
                service.domain = domain
                logger.debug(f"Domain inferred from git: {domain}")

    def _get_extended_stats(self, service_path: Optional[Path]) -> GitExtendedStats:
        """Extract extended git statistics."""
        stats = GitExtendedStats()
        
        if not self.is_git_repo:
            return stats
        
        # Get branches
        try:
            result = subprocess.run(
                ["git", "branch", "-r", "--format=%(refname:short)"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for branch in result.stdout.strip().split("\n"):
                    branch = branch.strip()
                    if not branch or "HEAD" in branch:
                        continue
                    stats.active_branches.append(branch)
                    branch_lower = branch.lower()
                    if any(kw in branch_lower for kw in ["feat", "feature", "add"]):
                        stats.feature_branches += 1
                    elif any(kw in branch_lower for kw in ["fix", "bug", "hotfix", "patch"]):
                        stats.bugfix_branches += 1
        except Exception as e:
            logger.debug(f"Failed to get branches: {e}")
        
        # Get tags
        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-creatordate"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
                stats.tags = tags
                stats.tag_count = len(tags)
                if tags:
                    stats.latest_tag = tags[0]
        except Exception as e:
            logger.debug(f"Failed to get tags: {e}")
        
        # Get file hotspots (most changed files)
        try:
            cmd = ["git", "log", "--format=", "--name-only", "-n", "100"]
            if service_path:
                rel_path = service_path
                if service_path.is_absolute():
                    try:
                        rel_path = service_path.relative_to(self.repo_root)
                    except ValueError:
                        rel_path = service_path
                cmd.extend(["--", str(rel_path)])
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                file_counts: Counter[str] = Counter()
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("commit"):
                        file_counts[line] += 1
                stats.hotspot_files = file_counts.most_common(10)
        except Exception as e:
            logger.debug(f"Failed to get file hotspots: {e}")
        
        # Extract PR/Issue references from recent commits
        try:
            result = subprocess.run(
                ["git", "log", "--format=%s", "-n", "50"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                pr_pattern = re.compile(r"#(\d+)")
                issue_pattern = re.compile(r"(?:fix|fixes|close|closes|resolve|resolves)\s*#(\d+)", re.I)
                
                for line in result.stdout.split("\n"):
                    # Find all PR references
                    for match in pr_pattern.findall(line):
                        ref = f"#{match}"
                        if ref not in stats.pr_references:
                            stats.pr_references.append(ref)
                    # Find issue references
                    for match in issue_pattern.findall(line):
                        ref = f"#{match}"
                        if ref not in stats.issue_references:
                            stats.issue_references.append(ref)
        except Exception as e:
            logger.debug(f"Failed to extract PR/issue references: {e}")
        
        return stats

    def _infer_domain_from_git(
        self,
        service_path: Optional[Path],
        service_name: str,
    ) -> Optional[str]:
        """Infer domain from git commit messages and touched paths."""
        candidates: list[str] = []

        if service_path:
            candidates.extend(self._tokenize_parts(service_path.parts[-3:]))
        candidates.extend(self._tokenize_text(service_name))

        if not self.is_git_repo:
            return self._score_candidates(candidates)

        try:
            cmd = ["git", "log", "--format=%s", "--name-only", "-n", "200"]
            if service_path:
                rel_path = service_path
                if service_path.is_absolute():
                    try:
                        rel_path = service_path.relative_to(self.repo_root)
                    except ValueError:
                        rel_path = service_path
                cmd.extend(["--", str(rel_path)])

            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return self._score_candidates(candidates)

            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if "/" in stripped or "." in stripped:
                    candidates.extend(self._tokenize_text(stripped))
                else:
                    candidates.extend(self._tokenize_text(stripped))
        except Exception as exc:
            logger.debug("Git domain inference failed for %s: %s", service_name, exc)

        return self._score_candidates(candidates)

    def _tokenize_text(self, text: str) -> list[str]:
        """Split a string into lowercase tokens."""
        return [token.lower() for token in re.split(r"[^A-Za-z0-9]+", text) if token]

    def _tokenize_parts(self, parts: tuple[str, ...] | list[str]) -> list[str]:
        tokens: list[str] = []
        for part in parts:
            tokens.extend(self._tokenize_text(part))
        return tokens

    def _score_candidates(self, candidates: list[str]) -> Optional[str]:
        """Map candidate tokens to a domain using keyword scores."""
        if not candidates:
            return None

        scores: Counter[str] = Counter()
        for candidate in candidates:
            for domain, keywords in DOMAIN_KEYWORDS.items():
                if candidate == domain:
                    scores[domain] += 2
                elif any(candidate.startswith(k) or k in candidate for k in keywords):
                    scores[domain] += 1

        if not scores:
            return None
        return scores.most_common(1)[0][0]
