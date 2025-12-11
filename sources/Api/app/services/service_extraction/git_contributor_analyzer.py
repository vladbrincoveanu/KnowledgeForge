"""Git contributor analyzer to extract owner and commit statistics from git history."""

import logging
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContributorSummary:
    """Summary for a top contributor."""
    email: str
    name: Optional[str]
    commit_count: int


@dataclass
class GitContributorStats:
    """Statistics about contributors to a service."""
    top_contributors: list[ContributorSummary]
    unique_contributors: int
    total_commits: int
    last_commit_date: Optional[datetime]
    first_commit_date: Optional[datetime]
    
    # Commit type breakdown
    feature_commits: int   # "feat:", "feature", "add"
    bugfix_commits: int    # "fix:", "bug", "hotfix"
    chore_commits: int     # "chore:", "refactor", "docs"
    
    # Activity metrics
    commits_30d: int
    commits_90d: int
    commits_180d: int
    
    # Commit messages for analysis
    recent_commit_messages: list[str]


class GitContributorAnalyzer:
    """
    Analyze git commit history to extract:
    - Top contributors (for owner detection)
    - Commit statistics (for status inference)
    - Commit type breakdown (feature vs bugfix vs chore)
    """
    
    def __init__(self, repo_root: Path):
        """
        Initialize git contributor analyzer.
        
        Args:
            repo_root: Root path of the git repository
        """
        self.repo_root = Path(repo_root).resolve()
        self.is_git_repo = (self.repo_root / '.git').exists()
    
    def analyze_service_contributors(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None,
        max_contributors: int = 5
    ) -> Optional[GitContributorStats]:
        """
        Analyze git history for a specific service path.
        
        Args:
            service_path: Path to service directory/file (relative to repo root)
            service_name: Service name for searching in commit messages
            max_contributors: Maximum number of top contributors to return
        
        Returns:
            GitContributorStats with contributor and commit information
        """
        if not self.is_git_repo:
            logger.debug("Not a git repository, cannot analyze contributors")
            return None
        
        try:
            # Build git log command
            cmd = [
                'git', 'log',
                '--format=%H|%an|%ae|%ad|%s',  # hash|author|email|date|subject
                '--date=iso',
                '--all',
            ]
            
            # Add path filter if provided
            if service_path:
                rel_path = self._get_relative_path(service_path)
                if rel_path:
                    cmd.append('--')
                    cmd.append(str(rel_path))
            
            # Execute git log
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning(f"Git log failed: {result.stderr}")
                return None
            
            if not result.stdout.strip():
                logger.debug(f"No git history found for {service_path}")
                return None
            
            # Parse commits
            commits = []
            contributors = Counter()
            contributor_names: dict[str, Optional[str]] = {}
            now = datetime.now()
            thirty_days_ago = now - timedelta(days=30)
            ninety_days_ago = now - timedelta(days=90)
            one_eighty_days_ago = now - timedelta(days=180)
            
            feature_count = 0
            bugfix_count = 0
            chore_count = 0
            commits_30d = 0
            commits_90d = 0
            commits_180d = 0
            
            last_commit_date = None
            first_commit_date = None
            recent_messages = []
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|', 4)
                if len(parts) < 5:
                    continue
                
                commit_hash, author_name, email, date_str, message = parts
                author_name = author_name.strip() if author_name else None
                
                try:
                    # Parse ISO date format: "2024-12-08 15:30:45 +0000" or "2024-12-08T15:30:45+00:00"
                    date_str_clean = date_str.replace(' ', 'T', 1)
                    # Remove timezone offset for parsing
                    if '+' in date_str_clean:
                        date_str_clean = date_str_clean.split('+')[0].strip()
                    elif '-' in date_str_clean and date_str_clean.count('-') > 2:
                        # Handle format like "2024-12-08 15:30:45 -0500"
                        # Keep the date and time part before the timezone
                        parts = date_str.split()
                        if len(parts) >= 2:
                            date_str_clean = f"{parts[0]}T{parts[1]}"
                        else:
                            date_str_clean = date_str.split('+')[0].split('-')[0].strip()
                    
                    commit_date = datetime.fromisoformat(date_str_clean)
                except (ValueError, IndexError):
                    try:
                        # BUG FIX: Remove timezone first, then parse
                        clean_date = date_str.split('+')[0].strip()
                        commit_date = datetime.strptime(clean_date, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        logger.debug(f"Could not parse date: {date_str}")
                        continue
                
                # Track first and last commit dates
                if first_commit_date is None or commit_date < first_commit_date:
                    first_commit_date = commit_date
                if last_commit_date is None or commit_date > last_commit_date:
                    last_commit_date = commit_date
                
                # Count contributors
                contributors[email] += 1
                if email not in contributor_names and author_name:
                    contributor_names[email] = author_name
                
                # Categorize commit type
                message_lower = message.lower()
                if any(keyword in message_lower for keyword in ['feat', 'feature', 'add', 'new', 'implement']):
                    feature_count += 1
                elif any(keyword in message_lower for keyword in ['fix', 'bug', 'hotfix', 'patch', 'resolve']):
                    bugfix_count += 1
                elif any(keyword in message_lower for keyword in ['chore', 'refactor', 'docs', 'style', 'test']):
                    chore_count += 1
                
                # Count commits by time period
                if commit_date >= thirty_days_ago:
                    commits_30d += 1
                    if len(recent_messages) < 10:  # Keep last 10 messages
                        recent_messages.append(message)
                if commit_date >= ninety_days_ago:
                    commits_90d += 1
                if commit_date >= one_eighty_days_ago:
                    commits_180d += 1
                
                commits.append({
                    'hash': commit_hash,
                    'email': email,
                    'date': commit_date,
                    'message': message,
                })
            
            # Get top contributors
            top_contributors_raw = contributors.most_common(max_contributors)
            top_contributors = [
                ContributorSummary(
                    email=email,
                    name=contributor_names.get(email),
                    commit_count=count,
                )
                for email, count in top_contributors_raw
            ]
            
            stats = GitContributorStats(
                top_contributors=top_contributors,
                unique_contributors=len(contributors),
                total_commits=len(commits),
                last_commit_date=last_commit_date,
                first_commit_date=first_commit_date,
                feature_commits=feature_count,
                bugfix_commits=bugfix_count,
                chore_commits=chore_count,
                commits_30d=commits_30d,
                commits_90d=commits_90d,
                commits_180d=commits_180d,
                recent_commit_messages=recent_messages,
            )
            
            logger.debug(
                f"Analyzed {len(commits)} commits for {service_path}: "
                f"{commits_30d} in 30d, top contributor: {top_contributors[0].email if top_contributors else 'N/A'}"
            )
            
            return stats
        
        except subprocess.TimeoutExpired:
            logger.warning(f"Git log timeout for {service_path}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing git contributors for {service_path}: {e}", exc_info=True)
            return None
    
    def extract_owner(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None,
    ) -> tuple[Optional[str], list[str]]:
        """
        Extract owner from top git contributors.
        
        Args:
            service_path: Path to service directory/file
            service_name: Service name
        
        Returns:
            (primary_owner_name, list_of_top_contributor_emails)
            Note: primary_owner_name uses the contributor's name if available, 
            otherwise falls back to email
        """
        stats = self.analyze_service_contributors(service_path, service_name)
        
        if not stats or not stats.top_contributors:
            return None, []
        
        # Primary owner is the top contributor - use name if available, fallback to email
        top_contributor = stats.top_contributors[0]
        primary_owner = top_contributor.name or top_contributor.email
        
        # All top contributors (for owner_contributors field)
        all_contributors = [contributor.email for contributor in stats.top_contributors]
        
        return primary_owner, all_contributors
    
    def _get_relative_path(self, service_path: Path) -> Optional[Path]:
        """Convert service path to relative path from repo root."""
        try:
            service_path = Path(service_path)
            
            # If already relative, use as-is
            if not service_path.is_absolute():
                rel_path = service_path
            else:
                # Make relative to repo root
                rel_path = service_path.relative_to(self.repo_root)
            
            # Ensure it exists in the repo
            full_path = self.repo_root / rel_path
            if full_path.exists():
                return rel_path
            
            # Try parent directory if it's a file
            if rel_path.is_file() or '.' in rel_path.name:
                parent = rel_path.parent
                if (self.repo_root / parent).exists():
                    return parent
            
            return rel_path
        
        except (ValueError, AttributeError):
            # Path is not relative to repo root, try to find it
            if service_path.is_absolute():
                return None
            
            # Assume it's already relative
            return service_path
