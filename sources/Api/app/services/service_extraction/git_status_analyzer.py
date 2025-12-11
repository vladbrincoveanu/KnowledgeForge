"""Git log analyzer to determine service status from commit history."""

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.domain.models.services import ServiceStatus
from app.services.service_extraction.git_contributor_analyzer import (
    GitContributorAnalyzer,
    GitContributorStats,
)

logger = logging.getLogger(__name__)


class GitStatusAnalyzer:
    """
    Analyze git commit history to infer service lifecycle status.
    
    Heuristics:
    - Active-Dev: Recent commits (within 30 days), frequent commits
    - Maintenance-Only: Old commits (30-180 days), only bugfixes/maintenance keywords
    - Deprecated: Very old commits (>180 days) or explicit deprecation messages
    """
    
    def __init__(self, repo_root: Path):
        """
        Initialize git status analyzer.
        
        Args:
            repo_root: Root path of the git repository
        """
        self.repo_root = Path(repo_root).resolve()
        self.is_git_repo = (self.repo_root / '.git').exists()
        self.contributor_analyzer = GitContributorAnalyzer(repo_root)
    
    def analyze_service_status(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None
    ) -> ServiceStatus:
        """
        Analyze git history to determine service status.
        
        Enhanced with commit type analysis (feature vs bugfix).
        
        Args:
            service_path: Path to service directory/file (relative to repo root)
            service_name: Service name for searching in commit messages
        
        Returns:
            Inferred ServiceStatus based on git activity
        """
        if not self.is_git_repo:
            logger.debug("Not a git repository, cannot analyze git history")
            return ServiceStatus.UNKNOWN
        
        try:
            # Get commit statistics
            commit_stats = self._get_commit_stats(service_path, service_name)
            
            if not commit_stats:
                return ServiceStatus.UNKNOWN
            
            # Check for explicit deprecation in commit messages
            if self._has_deprecation_keywords(service_path, service_name):
                return ServiceStatus.DEPRECATED
            
            # Get contributor stats for enhanced analysis
            contributor_stats = self.contributor_analyzer.analyze_service_contributors(
                service_path=service_path,
                service_name=service_name,
            )
            
            # Analyze commit frequency and recency with commit types
            return self._infer_status_from_activity(commit_stats, contributor_stats)
        
        except Exception as e:
            logger.warning(f"Failed to analyze git status: {e}")
            return ServiceStatus.UNKNOWN
    
    def _get_commit_stats(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get commit statistics for a service.
        
        Returns:
            Dict with 'total_commits', 'last_commit_date', 'recent_commits', 'days_since_last'
        """
        try:
            # Build git log command
            cmd = ['git', 'log', '--all', '--format=%H|%ai|%s', '--date=iso']
            
            # If service_path is provided, limit to that path
            if service_path:
                rel_path = str(service_path.relative_to(self.repo_root)) if service_path.is_absolute() else str(service_path)
                cmd.append('--')
                cmd.append(rel_path)
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return None
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|', 2)
                if len(parts) >= 2:
                    commit_hash = parts[0]
                    commit_date_str = parts[1]
                    commit_message = parts[2] if len(parts) > 2 else ''
                    
                    try:
                        # Parse ISO date format: "2024-12-08 15:30:45 +0000" or "2024-12-08T15:30:45+00:00"
                        date_str = commit_date_str.replace(' ', 'T', 1)
                        # Remove timezone offset for parsing
                        if '+' in date_str:
                            date_str = date_str.split('+')[0].strip()
                        elif date_str.count('-') > 2:
                            # Handle format like "2024-12-08 15:30:45 -0500"
                            parts = date_str.split(' ')
                            if len(parts) >= 2:
                                date_str = 'T'.join(parts[:2])
                        
                        commit_date = datetime.fromisoformat(date_str)
                        commits.append({
                            'hash': commit_hash,
                            'date': commit_date,
                            'message': commit_message.lower()
                        })
                    except Exception as e:
                        logger.debug(f"Failed to parse commit date '{commit_date_str}': {e}")
                        continue
            
            if not commits:
                return None
            
            # Sort by date (newest first)
            commits.sort(key=lambda x: x['date'], reverse=True)
            
            last_commit = commits[0]
            now = datetime.now()
            days_since_last = (now - last_commit['date']).days
            
            # Count recent commits (last 30 days)
            recent_cutoff = now - timedelta(days=30)
            recent_commits = sum(1 for c in commits if c['date'] > recent_cutoff)
            
            # Count maintenance commits (bugfix, fix, patch, maintenance keywords)
            maintenance_keywords = ['fix', 'bug', 'patch', 'maintenance', 'maint', 'bugfix', 'hotfix']
            maintenance_commits = sum(
                1 for c in commits[:10]  # Check last 10 commits
                if any(keyword in c['message'] for keyword in maintenance_keywords)
            )
            
            return {
                'total_commits': len(commits),
                'last_commit_date': last_commit['date'],
                'days_since_last': days_since_last,
                'recent_commits': recent_commits,
                'maintenance_commits': maintenance_commits,
                'commits': commits[:20]  # Keep last 20 for analysis
            }
        
        except subprocess.TimeoutExpired:
            logger.warning("Git log command timed out")
            return None
        except Exception as e:
            logger.debug(f"Failed to get commit stats: {e}")
            return None
    
    def _has_deprecation_keywords(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None
    ) -> bool:
        """
        Check if commit messages contain deprecation keywords.
        
        Returns:
            True if deprecation keywords found in recent commits
        """
        try:
            cmd = ['git', 'log', '--all', '--format=%s', '--date=iso', '-n', '50']
            
            if service_path:
                rel_path = str(service_path.relative_to(self.repo_root)) if service_path.is_absolute() else str(service_path)
                cmd.append('--')
                cmd.append(rel_path)
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                return False
            
            deprecation_keywords = [
                'deprecat', 'sunset', 'retire', 'remove', 'delete',
                'legacy', 'old', 'unused', 'dead', 'frozen', 'eol',
                'end of life', 'end-of-life'
            ]
            
            messages = result.stdout.lower()
            
            # Check for deprecation keywords
            for keyword in deprecation_keywords:
                if keyword in messages:
                    return True
            
            # Check if service name is mentioned with deprecation context
            if service_name:
                service_lower = service_name.lower()
                for keyword in deprecation_keywords:
                    if f"{service_lower}" in messages and keyword in messages:
                        return True
            
            return False
        
        except Exception as e:
            logger.debug(f"Failed to check deprecation keywords: {e}")
            return False
    
    def _infer_status_from_activity(
        self, 
        commit_stats: dict,
        contributor_stats: Optional[GitContributorStats] = None
    ) -> ServiceStatus:
        """
        Infer service status from commit activity patterns.
        
        Enhanced with commit type analysis (feature vs bugfix vs chore).
        
        Args:
            commit_stats: Commit statistics dictionary
            contributor_stats: Optional GitContributorStats with commit type breakdown
        
        Returns:
            Inferred ServiceStatus
        """
        days_since_last = commit_stats['days_since_last']
        recent_commits = commit_stats['recent_commits']
        maintenance_commits = commit_stats['maintenance_commits']
        total_commits = commit_stats['total_commits']
        
        # Use contributor stats if available (more accurate)
        if contributor_stats:
            commits_30d = contributor_stats.commits_30d
            commits_90d = contributor_stats.commits_90d
            commits_180d = contributor_stats.commits_180d
            feature_count = contributor_stats.feature_commits
            bugfix_count = contributor_stats.bugfix_commits
            
            # Very old (>180 days) = likely deprecated
            if commits_180d == 0:
                return ServiceStatus.DEPRECATED
            
            # Recent activity (<30 days)
            if commits_30d > 0:
                # Calculate feature ratio
                total_recent = feature_count + bugfix_count + contributor_stats.chore_commits
                if total_recent > 0:
                    feature_ratio = feature_count / total_recent
                    
                    # Active-Dev: Recent commits + more features than bugfixes
                    if commits_30d >= 3 and feature_ratio > 0.4:
                        return ServiceStatus.ACTIVE_DEV
                    # Maintenance: Recent commits but mostly bugfixes
                    elif bugfix_count > feature_count:
                        return ServiceStatus.MAINTENANCE_ONLY
                    # Active-Dev: Some features even if fewer
                    elif feature_count > 0:
                        return ServiceStatus.ACTIVE_DEV
            
            # Old activity (30-180 days)
            if commits_90d > 0 and commits_30d == 0:
                # Had activity 30-90 days ago, but not recently
                if bugfix_count > feature_count:
                    return ServiceStatus.MAINTENANCE_ONLY
                else:
                    return ServiceStatus.MAINTENANCE_ONLY  # Still maintenance if no recent activity
            
            # Very old (>180 days)
            if commits_180d == 0:
                return ServiceStatus.DEPRECATED
        
        # Fallback to original logic if no contributor stats
        # Very old (>180 days) = likely deprecated
        if days_since_last > 180:
            return ServiceStatus.DEPRECATED
        
        # Old (30-180 days) with only maintenance commits = maintenance-only
        if 30 < days_since_last <= 180:
            if maintenance_commits > 0 and recent_commits == 0:
                return ServiceStatus.MAINTENANCE_ONLY
            elif recent_commits == 0:
                # No commits in last 30 days, but had commits 30-180 days ago
                return ServiceStatus.MAINTENANCE_ONLY
        
        # Recent commits (<30 days) = active
        if days_since_last <= 30:
            if recent_commits >= 3:
                # Multiple recent commits = active development
                return ServiceStatus.ACTIVE_DEV
            elif recent_commits > 0:
                # Some recent activity
                # Check if it's mostly maintenance
                if maintenance_commits >= recent_commits * 0.7:
                    return ServiceStatus.MAINTENANCE_ONLY
                else:
                    return ServiceStatus.ACTIVE_DEV
        
        # Default to maintenance if we have some history but it's old
        if total_commits > 0:
            return ServiceStatus.MAINTENANCE_ONLY
        
        return ServiceStatus.UNKNOWN
    
    def get_service_activity_summary(
        self,
        service_path: Optional[Path] = None,
        service_name: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get detailed activity summary for a service.
        
        Returns:
            Dict with activity metrics and inferred status
        """
        if not self.is_git_repo:
            return None
        
        commit_stats = self._get_commit_stats(service_path, service_name)
        if not commit_stats:
            return None
        
        inferred_status = self._infer_status_from_activity(commit_stats)
        has_deprecation = self._has_deprecation_keywords(service_path, service_name)
        
        # Override with deprecation if found
        if has_deprecation:
            inferred_status = ServiceStatus.DEPRECATED
        
        return {
            'status': inferred_status.value,
            'total_commits': commit_stats['total_commits'],
            'last_commit_date': commit_stats['last_commit_date'].isoformat(),
            'days_since_last': commit_stats['days_since_last'],
            'recent_commits_30d': commit_stats['recent_commits'],
            'maintenance_commits': commit_stats['maintenance_commits'],
            'has_deprecation_keywords': has_deprecation,
        }

