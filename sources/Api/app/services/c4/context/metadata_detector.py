"""IT Landscape metadata detection for C4 Context level.

Detects:
- Owner team (from CODEOWNERS, git contributors, README)
- Business domain (Infrastructure, AI/ML, Data, etc.)
- Criticality tier (Tier 1/2/3)
- Data classification (PII, Credit-Card, Legal, General)
- Service status (Active-Dev, Maintenance-Only, Deprecated)
- Active experts count (bus factor indicator)
- Compliance risk level
- Git activity metrics
- Contributor statistics
"""

import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import tomli

logger = logging.getLogger(__name__)


class MetadataDetector:
    """Detects IT Landscape metadata for C4 Context."""

    def __init__(self, repo_path: Path, llm_manager=None, containers: dict[str, Any] = None):
        """Initialize metadata detector.

        Args:
            repo_path: Path to repository
            llm_manager: Optional LLM for team name suggestions
            containers: Optional dictionary of detected containers
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        self.containers = containers or {}

    def detect_owner_team(self) -> str:
        """Detect owner team from CODEOWNERS, README, or git contributors."""
        logger.info(f"Detecting owner team for repository at {self.repo_path}")
        
        # Check CODEOWNERS file
        codeowners_paths = [
            self.repo_path / "CODEOWNERS",
            self.repo_path / ".github" / "CODEOWNERS",
            self.repo_path / "docs" / "CODEOWNERS",
        ]

        for codeowners_file in codeowners_paths:
            if codeowners_file.exists():
                logger.info(f"Found CODEOWNERS file at {codeowners_file}")
                try:
                    with open(codeowners_file) as f:
                        content = f.read()

                    # Find @team mentions
                    team_pattern = r'@([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)'
                    teams = re.findall(team_pattern, content)

                    if teams:
                        logger.info(f"Found team in CODEOWNERS: {teams[0]}")
                        return teams[0]

                except Exception as e:
                    logger.warning(f"Failed to read CODEOWNERS: {e}")
                    pass

        # Check README for maintainers or team info
        readme_paths = [
            self.repo_path / "README.md",
            self.repo_path / "README.rst",
            self.repo_path / "README.txt",
        ]

        for readme in readme_paths:
            if readme.exists():
                logger.info(f"Checking README at {readme}")
                try:
                    with open(readme) as f:
                        content = f.read()

                    # Look for maintainers section
                    maintainer_patterns = [
                        r'maintainer[s]?:\s*(.+)',
                        r'owner[s]?:\s*(.+)',
                        r'team:\s*(.+)',
                        r'contact:\s*(.+)',
                        r'#([a-z0-9_-]+)',  # Slack channel
                    ]

                    for pattern in maintainer_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            team_info = match.group(1).strip()
                            if len(team_info) < 50:
                                logger.info(f"Found team in README: {team_info}")
                                return team_info

                except Exception as e:
                    logger.warning(f"Failed to read README: {e}")
                    pass

        # Fallback: Get top contributors from git
        logger.info("No CODEOWNERS or README team found, checking git contributors")
        top_contributors = self._get_top_git_contributors(max_contributors=5)

        # Try LLM enrichment first if available
        if top_contributors and self.llm_manager:
            logger.info(f"Asking LLM to suggest team name from {len(top_contributors)} contributors")
            suggested_team = self._suggest_team_name_from_contributors(top_contributors)
            if suggested_team and suggested_team != "Unknown":
                logger.info(f"LLM suggested team: {suggested_team}")
                return suggested_team

        # If git contributors found but no LLM, use top contributor
        if top_contributors:
            logger.info(f"Using top contributor from git: {top_contributors[0]}")
            first_contributor = top_contributors[0]
            first_email = first_contributor[0]

            # Try to extract name from git log
            try:
                result = subprocess.run(
                    ['git', 'log', '--format=%an', f'--author={first_email}', '-1'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    author_name = result.stdout.strip()
                    logger.info(f"Found author name from git: {author_name}")
                    return author_name
            except Exception as e:
                logger.warning(f"Failed to get author name: {e}")
                pass

            # Extract domain from email
            email_match = re.search(r'@([^.]+)', first_email)
            if email_match:
                domain = email_match.group(1)
                domain = domain.replace('-', ' ').replace('_', ' ').title()
                logger.info(f"Extracted domain from email: {domain}")
                return domain

            logger.info(f"Returning email as owner: {first_email}")
            return first_email

        logger.warning("No owner detected, returning 'Unassigned'")
        return "Unassigned"

    def _get_top_git_contributors(self, max_contributors: int = 3) -> list[tuple[str, int]]:
        """Get top contributors from git history."""
        if not (self.repo_path / ".git").exists():
            logger.warning(f"No .git directory found at {self.repo_path}")
            return []

        try:
            logger.info(f"Getting git contributors from {self.repo_path}")
            result = subprocess.run(
                ['git', 'shortlog', '-sne', '--all'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"Git shortlog failed with code {result.returncode}: {result.stderr}")
                return []

            logger.info(f"Git shortlog output: {result.stdout[:500]}...")  # Log first 500 chars
            
            contributors = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                match = re.search(r'\s+(\d+)\s+(.+?)(?:\s+<([^>]+)>)?$', line)
                if match:
                    commit_count = int(match.group(1))
                    name = match.group(2).strip()
                    email = match.group(3) if match.group(3) else name
                    contributors.append((email, commit_count))

            contributors.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Found {len(contributors)} contributors, returning top {max_contributors}")
            return contributors[:max_contributors]

        except Exception as e:
            logger.error(f"Failed to get git contributors: {e}", exc_info=True)
            return []

    def _suggest_team_name_from_contributors(self, contributors: list[tuple[str, int]]) -> Optional[str]:
        """Use LLM to suggest a team name from contributor emails."""
        llm = self.llm_manager
        if llm is None or not contributors:
            return None

        contributor_list = ", ".join([f"{email} ({count} commits)" for email, count in contributors])

        prompt = f"""Given these top git contributors to a repository:
{contributor_list}

Suggest a likely team name or owner group name for this repository. 
Consider email domains, naming patterns, and common team structures.

Return ONLY the team name (e.g., "backend-team", "platform-engineering", "data-team"), nothing else.
If uncertain, return the email domain of the top contributor.

Team name:"""

        try:
            response = llm.generate_text(
                prompt,
                max_tokens=50,
                temperature=0.3,
                use_cache=True
            )

            if response:
                team_name = response.strip().strip('"').strip("'")
                team_name = re.sub(r'^[^a-zA-Z0-9_-]+', '', team_name)
                team_name = re.sub(r'[^a-zA-Z0-9_-]+$', '', team_name)

                if team_name and len(team_name) < 50:
                    return team_name

        except Exception as e:
            logger.debug(f"LLM team name suggestion failed: {e}")

        return None

    def infer_business_domain(self) -> str:
        """Infer business domain from repository indicators."""
        indicators = {
            'infrastructure': 0,
            'ai_ml': 0,
            'data_engineering': 0,
            'user_management': 0,
            'api_gateway': 0,
            'developer_tools': 0,
        }

        # Check directory names
        dirs = [d.name.lower() for d in self.repo_path.iterdir() if d.is_dir()]
        dir_text = ' '.join(dirs)

        # Infrastructure indicators
        if any(k in dir_text for k in ['kubernetes', 'k8s', 'helm', 'terraform', 'docker', 'infra', 'deploy']):
            indicators['infrastructure'] += 3

        # AI/ML indicators
        if any(k in dir_text for k in ['ml', 'model', 'train', 'pipeline', 'kubeflow', 'clearml', 'mlops']):
            indicators['ai_ml'] += 3

        # Data engineering indicators
        if any(k in dir_text for k in ['data', 'etl', 'warehouse', 'analytics', 'kafka', 'spark']):
            indicators['data_engineering'] += 3

        # User management indicators
        if any(k in dir_text for k in ['auth', 'user', 'login', 'permission', 'oauth', 'identity']):
            indicators['user_management'] += 3

        # API gateway indicators
        if any(k in dir_text for k in ['gateway', 'proxy', 'ingress', 'router', 'apisix', 'kong']):
            indicators['api_gateway'] += 3

        # Developer tools indicators
        if any(k in dir_text for k in ['ci', 'cd', 'test', 'build', 'jenkins', 'gitlab', 'github']):
            indicators['developer_tools'] += 2

        # Check dependencies
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'rb') as f:
                    content = tomli.load(f)
                    deps_text = str(content).lower()

                    if 'tensorflow' in deps_text or 'pytorch' in deps_text or 'sklearn' in deps_text:
                        indicators['ai_ml'] += 2
                    if 'kubernetes' in deps_text or 'docker' in deps_text:
                        indicators['infrastructure'] += 1
                    if 'pandas' in deps_text or 'spark' in deps_text:
                        indicators['data_engineering'] += 2
                    if 'fastapi' in deps_text or 'flask' in deps_text:
                        indicators['api_gateway'] += 1

            except Exception:
                pass

        # Check container names
        for container_name in self.containers.keys():
            name_lower = container_name.lower()

            if any(k in name_lower for k in ['ml', 'model', 'train', 'pipeline', 'job', 'worker']):
                indicators['ai_ml'] += 2

            if any(k in name_lower for k in ['gateway', 'proxy', 'router', 'ingress', 'api']):
                indicators['api_gateway'] += 2

            if any(k in name_lower for k in ['harbor', 'registry', 'vault', 'monitoring', 'logging']):
                indicators['infrastructure'] += 2

            if any(k in name_lower for k in ['data', 'warehouse', 'lake', 'etl', 'analytics']):
                indicators['data_engineering'] += 2

            if any(k in name_lower for k in ['auth', 'iam', 'identity', 'user', 'account', 'login']):
                indicators['user_management'] += 2

        if not any(indicators.values()):
            return "General"

        domain_map = {
            'infrastructure': 'Infrastructure',
            'ai_ml': 'AI/ML Processing',
            'data_engineering': 'Data Engineering',
            'user_management': 'User Management',
            'api_gateway': 'API Gateway',
            'developer_tools': 'Developer Tools',
        }

        max_domain = max(indicators.items(), key=lambda x: x[1])
        return domain_map.get(max_domain[0], 'General')

    def determine_criticality(self) -> str:
        """Determine system criticality tier."""
        criticality_score = 0

        prod_indicators = [
            'prod', 'production', 'live', 'master', 'main',
            'sla', 'uptime', 'ha', 'high-availability',
            'monitoring', 'alerting', 'pagerduty',
        ]

        # Check containers for production indicators
        for container in self.containers.values():
            if 'path' in container:
                path_text = container['path'].lower()
                if any(ind in path_text for ind in prod_indicators):
                    criticality_score += 2

        # Check values.yaml for production config
        for values_file in self.repo_path.rglob("values.yaml"):
            try:
                with open(values_file) as f:
                    content = f.read().lower()

                if 'production' in content or 'prod' in content:
                    criticality_score += 2

                if 'replicas: 3' in content or 'replicas: 5' in content:
                    criticality_score += 1

                if 'resources:' in content and 'limits:' in content:
                    criticality_score += 1

                if 'prometheus' in content or 'grafana' in content or 'alert' in content:
                    criticality_score += 1

            except Exception:
                continue

        # Check README for SLA mentions
        readme = self.repo_path / "README.md"
        if readme.exists():
            try:
                with open(readme) as f:
                    content = f.read().lower()

                if 'sla' in content or 'service level' in content:
                    criticality_score += 3
                if 'critical' in content or 'production' in content:
                    criticality_score += 2
                if 'tier 1' in content or 'tier-1' in content:
                    criticality_score += 3

            except Exception:
                pass

        # Check for CI/CD presence
        ci_files = [
            self.repo_path / ".github" / "workflows",
            self.repo_path / ".gitlab-ci.yml",
            self.repo_path / "Jenkinsfile",
        ]

        has_cicd = any(f.exists() for f in ci_files)
        if has_cicd:
            criticality_score += 1

        # Determine tier
        if criticality_score >= 6:
            return "Tier 1 - Production Critical"
        elif criticality_score >= 3:
            return "Tier 2 - Production Standard"
        else:
            return "Tier 3 - Development/Internal"

    def infer_data_classification(self) -> str:
        """Infer data classification based on data handling patterns."""
        data_indicators = {
            'pii': 0,
            'financial': 0,
            'legal': 0,
        }

        sensitive_keywords = {
            'pii': ['email', 'phone', 'address', 'name', 'user', 'customer', 'profile', 'gdpr', 'ccpa'],
            'financial': ['payment', 'credit', 'card', 'invoice', 'transaction', 'billing', 'stripe', 'paypal'],
            'legal': ['compliance', 'audit', 'legal', 'security', 'encryption', 'auth', 'permission'],
        }

        # Scan Python files
        for py_file in self.repo_path.rglob("*.py"):
            if any(part in str(py_file) for part in ['.git', 'node_modules', '__pycache__', 'test']):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read(5000).lower()

                for category, keywords in sensitive_keywords.items():
                    for keyword in keywords:
                        if keyword in content:
                            data_indicators[category] += 1
            except Exception:
                continue

        # Check config files
        env_files = ['.env.example', '.env.template', 'config.yaml', 'docker-compose.yml']
        for env_file in env_files:
            file_path = self.repo_path / env_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()

                    for category, keywords in sensitive_keywords.items():
                        for keyword in keywords:
                            if keyword in content:
                                data_indicators[category] += 1
                except Exception:
                    continue

        # Determine classification
        if data_indicators['financial'] >= 3:
            return "Credit-Card"
        elif data_indicators['pii'] >= 5:
            return "PII"
        elif data_indicators['legal'] >= 3:
            return "Legal/Security"
        else:
            return "General"

    def detect_service_status(self) -> tuple[str, Optional[dict[str, Any]]]:
        """Detect service status based on git activity.

        Returns:
            Tuple of (status_string, evidence_dict)
            Status: "Active-Dev", "Maintenance-Only", "Deprecated / Frozen", or "unknown"
        """
        if not (self.repo_path / ".git").exists():
            return ("unknown", None)

        try:
            # Get commit counts for different periods
            def count_commits_since(days: int) -> int:
                result = subprocess.run(
                    ['git', 'log', f'--since={days}.days', '--oneline'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return len([line for line in result.stdout.strip().split('\n') if line.strip()])
                return 0

            commits_30d = count_commits_since(30)
            commits_90d = count_commits_since(90)
            commits_180d = count_commits_since(180)

            # Get last commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cI'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            last_commit_str = None
            days_since_last_commit = None
            if result.returncode == 0 and result.stdout.strip():
                last_commit_str = result.stdout.strip()
                try:
                    last_commit = datetime.fromisoformat(last_commit_str.replace('Z', '+00:00'))
                    days_since_last_commit = (datetime.now(last_commit.tzinfo) - last_commit).days
                except Exception:
                    pass

            evidence = {
                "commits_30d": commits_30d,
                "commits_90d": commits_90d,
                "commits_180d": commits_180d,
                "last_commit_date": last_commit_str,
                "days_since_last_commit": days_since_last_commit,
            }

            # Determine status based on activity
            # Active-Dev: Regular commits (5+ in last 30 days OR 10+ in last 90 days)
            if commits_30d >= 5 or commits_90d >= 10:
                return ("Active-Dev", evidence)

            # Deprecated/Frozen: No commits in 180+ days
            elif days_since_last_commit and days_since_last_commit > 180:
                return ("Deprecated / Frozen", evidence)

            # Maintenance-Only: Some activity but not actively developed
            elif commits_180d > 0:
                return ("Maintenance-Only", evidence)

            else:
                return ("unknown", evidence)

        except Exception as e:
            logger.debug(f"Failed to determine service status: {e}")
            return ("unknown", None)

    def calculate_active_experts(self) -> int:
        """Calculate number of active experts (bus factor indicator).

        Returns count of contributors with 3+ commits in last 90 days.
        """
        if not (self.repo_path / ".git").exists():
            return 0

        try:
            # Get contributors in last 90 days with commit counts
            result = subprocess.run(
                ['git', 'shortlog', '-sne', '--since=90.days'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return 0

            active_experts = 0
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                match = re.search(r'\s+(\d+)\s+', line)
                if match:
                    commit_count = int(match.group(1))
                    if commit_count >= 3:
                        active_experts += 1

            return active_experts

        except Exception as e:
            logger.debug(f"Failed to calculate active experts: {e}")
            return 0

    def assess_compliance_risk(self, domain: str, data_class: str, owner: str, tier: str) -> str:
        """Assess architectural compliance risk.

        Checks if sensitive data is properly prioritized and owned.

        Args:
            domain: Business domain
            owner: Owner team
            data_class: Data classification
            tier: Criticality tier

        Returns:
            "COMPLIANT", "AT_RISK", "NON_COMPLIANT", or "UNKNOWN"
        """
        # Extract tier number if present (e.g., "Tier 1 - Production Critical" -> 1)
        tier_number = None
        tier_match = re.search(r'tier\s*(\d+)', tier.lower())
        if tier_match:
            tier_number = int(tier_match.group(1))

        # High-risk data classifications
        high_risk_data = ["PII", "Credit-Card", "Legal/Security"]

        # Compliance rules:
        # 1. High-risk data (PII, Credit-Card) should be Tier 1 or 2
        # 2. High-risk data should have an assigned owner
        # 3. Tier 1 services should have an owner

        issues = []

        # Check if high-risk data is properly tiered
        if data_class in high_risk_data:
            if tier_number and tier_number >= 3:
                issues.append("high_risk_data_low_tier")

            if not owner or owner == "Unassigned":
                issues.append("high_risk_data_no_owner")

        # Check if Tier 1 has owner
        if tier_number == 1:
            if not owner or owner == "Unassigned":
                issues.append("tier1_no_owner")

        # Determine compliance level
        if not issues:
            return "COMPLIANT"
        elif len(issues) == 1:
            return "AT_RISK"
        elif len(issues) >= 2:
            return "NON_COMPLIANT"
        else:
            return "UNKNOWN"

    def get_git_activity_metrics(self) -> dict[str, Any]:
        """Get detailed git activity metrics.

        Returns:
            Dictionary with last_commit_date, commit_count_30d, 90d, 180d, contributor_count
        """
        if not (self.repo_path / ".git").exists():
            return {
                "last_commit_date": None,
                "commit_count_30d": 0,
                "commit_count_90d": 0,
                "commit_count_180d": 0,
                "contributor_count": 0,
            }

        try:
            # Get commit counts
            def count_commits_since(days: int) -> int:
                result = subprocess.run(
                    ['git', 'log', f'--since={days}.days', '--oneline'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return len([line for line in result.stdout.strip().split('\n') if line.strip()])
                return 0

            commits_30d = count_commits_since(30)
            commits_90d = count_commits_since(90)
            commits_180d = count_commits_since(180)

            # Get last commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cI'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            last_commit_date = None
            if result.returncode == 0 and result.stdout.strip():
                last_commit_date = result.stdout.strip()

            # Get unique contributor count
            result = subprocess.run(
                ['git', 'shortlog', '-sn', '--all'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            contributor_count = 0
            if result.returncode == 0:
                contributor_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])

            return {
                "last_commit_date": last_commit_date,
                "commit_count_30d": commits_30d,
                "commit_count_90d": commits_90d,
                "commit_count_180d": commits_180d,
                "contributor_count": contributor_count,
            }

        except Exception as e:
            logger.debug(f"Failed to get git activity metrics: {e}")
            return {
                "last_commit_date": None,
                "commit_count_30d": 0,
                "commit_count_90d": 0,
                "commit_count_180d": 0,
                "contributor_count": 0,
            }

    def get_owner_contributor_stats(self, max_contributors: int = 5) -> dict[str, Any]:
        """Get detailed owner and contributor statistics.

        Returns:
            Dictionary with owner, owner_contributors, owner_contributor_stats
        """
        contributors = self._get_top_git_contributors(max_contributors=max_contributors)

        if not contributors:
            return {
                "owner_contributors": [],
                "owner_contributor_stats": [],
            }

        # Format contributors for the Service model
        owner_contributors = [email for email, _ in contributors]
        owner_contributor_stats = [
            {
                "email": email,
                "name": self._get_contributor_name(email),
                "commit_count": count,
            }
            for email, count in contributors
        ]

        return {
            "owner_contributors": owner_contributors,
            "owner_contributor_stats": owner_contributor_stats,
        }

    def _get_contributor_name(self, email: str) -> str:
        """Get contributor name from email using git log."""
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%an', f'--author={email}', '-1'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback: extract name from email
        if '@' in email:
            return email.split('@')[0].replace('.', ' ').title()
        return email
