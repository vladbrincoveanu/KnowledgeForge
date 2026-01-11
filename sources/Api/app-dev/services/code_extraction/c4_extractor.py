"""C4 Model-based architecture extractor.

Implements the C4 Model approach to avoid information overload:
- Level 1 (Context): System + External dependencies
- Level 2 (Container): Deployable units (services, databases, frontends)
- Level 3 (Component): Public entry points only (not internal details)

Focus on architectural boundaries, not code details.
"""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict
from abc import ABC, abstractmethod

import yaml
import tomli

logger = logging.getLogger(__name__)


# ============================================================================
# Language Detector Strategy Pattern
# ============================================================================

class LanguageDetector(ABC):
    """Base class for language-specific entry point detection."""
    
    @abstractmethod
    def get_file_extensions(self) -> list[str]:
        """Return list of file extensions this detector handles."""
        pass
    
    @abstractmethod
    def get_entry_point_patterns(self) -> list[str]:
        """Return regex patterns for detecting entry points."""
        pass
    
    @abstractmethod
    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract entry points from file content.
        
        Args:
            file_path: Path to the source file
            content: File content as string
            
        Returns:
            List of entry point dictionaries with keys:
            - method: HTTP method (GET, POST, etc.) or None
            - path: Endpoint path or None
            - name: Function/class name
            - line_number: Line where found (optional)
        """
        pass
    
    def get_framework_manifests(self) -> list[str]:
        """Return list of framework manifest files that indicate this language."""
        return []


class PythonLanguageDetector(LanguageDetector):
    """Detector for Python frameworks (FastAPI, Flask, Django)."""
    
    def get_file_extensions(self) -> list[str]:
        return ['.py']
    
    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'@app\.(get|post|put|delete|patch)',
            r'@router\.(get|post|put|delete|patch)',
            r'@api\.(get|post|put|delete|patch)',
            r'class\s+\w+Controller',
            r'@Controller',
            r'@RestController',
        ]
    
    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract Python API endpoints."""
        entry_points = []
        
        # Find route decorators (FastAPI, Flask)
        route_pattern = r'@(?:app|router|api)\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)'
        matches = re.finditer(route_pattern, content)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Find function name after decorator
            func_pattern = r'def\s+(\w+)\s*\('
            remaining = content[match.end():]
            func_match = re.search(func_pattern, remaining[:200])
            
            if func_match:
                func_name = func_match.group(1)
                entry_points.append({
                    'method': method,
                    'path': path,
                    'name': func_name,
                    'line_number': content[:match.start()].count('\n') + 1,
                })
        
        return entry_points
    
    def get_framework_manifests(self) -> list[str]:
        return ['pyproject.toml', 'requirements.txt', 'setup.py', 'Pipfile']


class JavaScriptLanguageDetector(LanguageDetector):
    """Detector for JavaScript/TypeScript frameworks (Express, Next.js, etc.)."""
    
    def get_file_extensions(self) -> list[str]:
        return ['.js', '.jsx', '.ts', '.tsx']
    
    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'app\.(get|post|put|delete|patch)\(',
            r'router\.(get|post|put|delete|patch)\(',
            r'export\s+(async\s+)?function\s+handle',
            r'export\s+default\s+function',
        ]
    
    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract JavaScript/TypeScript API endpoints."""
        entry_points = []
        
        # Find route definitions (Express, etc.)
        route_pattern = r'(?:app|router)\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)'
        matches = re.finditer(route_pattern, content)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Try to find handler function name
            func_pattern = r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(|(\w+)\s*:\s*(?:async\s+)?\('
            remaining = content[match.end():match.end()+300]
            func_match = re.search(func_pattern, remaining)
            
            func_name = None
            if func_match:
                func_name = func_match.group(1) or func_match.group(2) or func_match.group(3)
            
            entry_points.append({
                'method': method,
                'path': path,
                'name': func_name or 'anonymous',
                'line_number': content[:match.start()].count('\n') + 1,
            })
        
        return entry_points
    
    def get_framework_manifests(self) -> list[str]:
        return ['package.json', 'yarn.lock', 'package-lock.json']


class JavaLanguageDetector(LanguageDetector):
    """Detector for Java frameworks (Spring Boot, etc.)."""
    
    def get_file_extensions(self) -> list[str]:
        return ['.java']
    
    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'@RestController',
            r'@Controller',
            r'@RequestMapping',
            r'@GetMapping',
            r'@PostMapping',
        ]
    
    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract Java REST controllers."""
        entry_points = []
        
        # Find controller classes
        if '@RestController' in content or '@Controller' in content:
            # Extract class name
            class_pattern = r'class\s+(\w+)'
            class_match = re.search(class_pattern, content)
            
            if class_match:
                class_name = class_match.group(1)
                
                # Find request mappings
                mapping_pattern = r'@(?:Get|Post|Put|Delete|Patch)Mapping\s*\(["\']([^"\']+)'
                mappings = re.finditer(mapping_pattern, content)
                
                for mapping in mappings:
                    path = mapping.group(1)
                    # Try to find method name
                    method_pattern = r'public\s+\w+\s+(\w+)\s*\('
                    method_match = re.search(method_pattern, content[mapping.end():mapping.end()+200])
                    method_name = method_match.group(1) if method_match else 'unknown'
                    
                    entry_points.append({
                        'method': 'GET',  # Default, could be enhanced
                        'path': path,
                        'name': f"{class_name}.{method_name}",
                        'line_number': content[:mapping.start()].count('\n') + 1,
                    })
                
                # If no specific mappings, just add the controller
                if not entry_points:
                    entry_points.append({
                        'method': None,
                        'path': None,
                        'name': class_name,
                        'line_number': content[:class_match.start()].count('\n') + 1,
                    })
        
        return entry_points
    
    def get_framework_manifests(self) -> list[str]:
        return ['pom.xml', 'build.gradle', 'build.gradle.kts']


class C4ArchitectureExtractor:
    """Extract architecture using C4 Model principles.
    
    Philosophy:
    - Extract architectural boundaries, not code details
    - Focus on entry/exit points (APIs, databases, external services)
    - Group by domain to avoid clutter
    - Use LLM only for system summaries
    """
    
    def __init__(self, repo_path: Path, llm_manager=None):
        """Initialize C4 extractor.
        
        Args:
            repo_path: Path to repository (will be resolved to absolute)
            llm_manager: Optional LLM for generating system summaries
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        
        # C4 Model data structures
        self.system_context = {}  # Level 1
        self.containers = {}       # Level 2
        self.components = {}       # Level 3
        
        # Language detectors (Strategy Pattern)
        self.language_detectors = [
            PythonLanguageDetector(),
            JavaScriptLanguageDetector(),
            JavaLanguageDetector(),
        ]
        
        # Framework manifest files that indicate a deployable service
        self.framework_manifests = {
            'Dockerfile',
            'docker-compose.yml',
            'docker-compose.yaml',
            'package.json',
            'pyproject.toml',
            'pom.xml',
            'build.gradle',
            'build.gradle.kts',
            'go.mod',
            'Cargo.toml',
            'requirements.txt',
            'Chart.yaml',
        }
    
    def extract(self, max_components_per_domain: int = 10) -> dict[str, Any]:
        """Extract C4 architecture.
        
        Args:
            max_components_per_domain: Group components if more than this
            
        Returns:
            C4 architecture with 3 levels
        """
        logger.info("Starting C4 Model extraction...")
        logger.info("="*80)
        
        # Level 2: Containers first (needed for domain detection)
        logger.info("\n📦 LEVEL 2: Containers")
        logger.info("-"*80)
        self._extract_level2_containers()
        logger.info(f"✓ Containers: {len(self.containers)}")
        
        # Map internal dependencies (creates connection lines)
        logger.info("\n🔗 Mapping Internal Dependencies")
        logger.info("-"*80)
        self._map_internal_dependencies()
        total_deps = sum(len(c.get('dependencies_internal', [])) for c in self.containers.values())
        logger.info(f"✓ Internal dependencies: {total_deps} connections")
        
        # Level 1: Context (System + External Dependencies + IT Landscape metadata)
        logger.info("\n📊 LEVEL 1: System Context")
        logger.info("-"*80)
        self._extract_level1_context()
        logger.info(f"✓ System: {self.system_context.get('name', 'Unknown')}")
        logger.info(f"✓ Owner: {self.system_context.get('owner_team', 'Unknown')}")
        logger.info(f"✓ Domain: {self.system_context.get('business_domain', 'Unknown')}")
        logger.info(f"✓ Criticality: {self.system_context.get('criticality', 'Unknown')}")
        logger.info(f"✓ External dependencies: {len(self.system_context.get('external_dependencies', []))}")
        
        # Level 3: Components (Public Entry Points Only)
        logger.info("\n🔌 LEVEL 3: Components")
        logger.info("-"*80)
        self._extract_level3_components()
        logger.info(f"✓ Components: {len(self.components)}")
        
        # Group by domain if too many
        if len(self.components) > max_components_per_domain:
            logger.info(f"✓ Grouping {len(self.components)} components by domain...")
            self._group_by_domain()
        
        # Build final structure
        c4_architecture = {
            "c4_model_version": "1.0",
            "system_context": self.system_context,
            "containers": list(self.containers.values()),
            "components": list(self.components.values()),
            "metadata": {
                "total_containers": len(self.containers),
                "total_components": len(self.components),
                "extraction_approach": "c4_model_focused"
            }
        }
        
        logger.info("\n" + "="*80)
        logger.info("✅ C4 Model Extraction Complete")
        logger.info("="*80)
        logger.info(f"Level 1 (Context): 1 system, {len(self.system_context.get('external_dependencies', []))} external deps")
        logger.info(f"Level 2 (Containers): {len(self.containers)} deployable units")
        logger.info(f"Level 3 (Components): {len(self.components)} public entry points")
        
        return c4_architecture
    
    def _extract_level1_context(self):
        """Extract Level 1: System Context.
        
        Identifies:
        - System name (from README, pyproject.toml, package.json)
        - System purpose (LLM-generated summary)
        - External dependencies (Stripe, AWS, databases)
        - Owner team (from CODEOWNERS, README)
        - Business domain (Infrastructure, AI Processing, etc.)
        - Criticality (Tier 1, 2, 3)
        """
        # Find system name
        system_name = self._detect_system_name()
        
        # Find external dependencies
        external_deps = self._detect_external_dependencies()
        
        # Generate system purpose with LLM (if available)
        system_purpose = self._generate_system_purpose()
        
        # IT Landscape metadata
        owner_team = self._detect_owner_team()
        business_domain = self._infer_business_domain()
        criticality = self._determine_criticality()
        
        self.system_context = {
            "c4_level": 1,
            "type": "system",
            "name": system_name,
            "purpose": system_purpose,
            "external_dependencies": external_deps,
            
            # IT Landscape fields
            "owner_team": owner_team,
            "business_domain": business_domain,
            "criticality": criticality,
        }
    
    def _detect_system_name(self) -> str:
        """Detect system name from project files."""
        # Try package.json
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    if 'name' in data:
                        return data['name']
            except Exception:
                pass
        
        # Try pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'rb') as f:
                    data = tomli.load(f)
                    if 'project' in data and 'name' in data['project']:
                        return data['project']['name']
                    if 'tool' in data and 'poetry' in data['tool']:
                        if 'name' in data['tool']['poetry']:
                            return data['tool']['poetry']['name']
            except Exception:
                pass
        
        # Try README.md
        readme = self.repo_path / "README.md"
        if readme.exists():
            try:
                with open(readme) as f:
                    first_line = f.readline().strip()
                    # Extract from # Title
                    if first_line.startswith('#'):
                        return first_line.lstrip('#').strip()
            except Exception:
                pass
        
        # Fallback to directory name
        return self.repo_path.name
    
    def _detect_external_dependencies(self) -> list[dict[str, Any]]:
        """Detect external service dependencies.
        
        Looks for:
        - Cloud providers (AWS, Azure, GCP)
        - Databases (PostgreSQL, MongoDB, Redis)
        - Payment providers (Stripe, PayPal)
        - Auth providers (Auth0, Okta)
        - APIs and SaaS services
        """
        external_deps = []
        
        # Parse dependencies from config files
        deps_from_configs = self._parse_dependency_files()
        
        # Detect from values.yaml (Helm charts)
        deps_from_helm = self._parse_helm_values()
        
        # Detect from .env files
        deps_from_env = self._parse_env_files()
        
        # Combine and deduplicate
        all_deps = deps_from_configs + deps_from_helm + deps_from_env
        
        # Deduplicate by name
        seen = set()
        for dep in all_deps:
            name = dep['name']
            if name not in seen:
                external_deps.append(dep)
                seen.add(name)
        
        return external_deps
    
    def _parse_dependency_files(self) -> list[dict[str, Any]]:
        """Parse package manifests for external dependencies."""
        deps = []
        
        # Known external services patterns
        external_patterns = {
            'stripe': ('Stripe', 'payment'),
            'aws': ('AWS', 'cloud'),
            's3': ('AWS S3', 'storage'),
            'postgres': ('PostgreSQL', 'database'),
            'mongodb': ('MongoDB', 'database'),
            'redis': ('Redis', 'cache'),
            'kafka': ('Kafka', 'messaging'),
            'rabbitmq': ('RabbitMQ', 'messaging'),
            'elasticsearch': ('Elasticsearch', 'search'),
            'auth0': ('Auth0', 'authentication'),
            'okta': ('Okta', 'authentication'),
            'sendgrid': ('SendGrid', 'email'),
            'twilio': ('Twilio', 'sms'),
            'slack': ('Slack', 'notifications'),
            'datadog': ('Datadog', 'monitoring'),
            'sentry': ('Sentry', 'error-tracking'),
        }
        
        # Scan pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'rb') as f:
                    data = tomli.load(f)
                    
                    # Check dependencies
                    project_deps = data.get('project', {}).get('dependencies', [])
                    poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
                    
                    all_deps_text = str(project_deps) + str(poetry_deps)
                    
                    for pattern, (name, dep_type) in external_patterns.items():
                        if pattern in all_deps_text.lower():
                            deps.append({
                                'name': name,
                                'type': dep_type,
                                'detected_from': 'pyproject.toml'
                            })
            except Exception as e:
                logger.debug(f"Error parsing pyproject.toml: {e}")
        
        # Scan package.json
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    
                    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                    all_deps_text = str(all_deps)
                    
                    for pattern, (name, dep_type) in external_patterns.items():
                        if pattern in all_deps_text.lower():
                            deps.append({
                                'name': name,
                                'type': dep_type,
                                'detected_from': 'package.json'
                            })
            except Exception as e:
                logger.debug(f"Error parsing package.json: {e}")
        
        return deps
    
    def _parse_helm_values(self) -> list[dict[str, Any]]:
        """Extract external services from Helm values."""
        deps = []
        
        values_files = list(self.repo_path.rglob("values.yaml"))
        
        for values_file in values_files:
            try:
                with open(values_file) as f:
                    data = yaml.safe_load(f)
                
                if not data:
                    continue
                
                # Look for external URLs
                external_urls = self._find_external_urls(data)
                
                for url in external_urls:
                    # Extract service name from URL
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': str(values_file.relative_to(self.repo_path))
                    })
            
            except Exception as e:
                logger.debug(f"Error parsing {values_file}: {e}")
        
        return deps
    
    def _parse_env_files(self) -> list[dict[str, Any]]:
        """Parse .env files for external service references."""
        deps = []
        
        env_files = list(self.repo_path.glob("*.env")) + list(self.repo_path.glob(".env*"))
        
        url_pattern = r'https?://[^\s"\']+'
        
        for env_file in env_files:
            try:
                with open(env_file, 'r') as f:
                    content = f.read()
                
                # Find URLs
                urls = re.findall(url_pattern, content)
                
                for url in urls:
                    name = self._extract_service_name_from_url(url)
                    deps.append({
                        'name': name,
                        'type': 'external_service',
                        'url': url,
                        'detected_from': env_file.name
                    })
            
            except Exception:
                pass
        
        return deps
    
    def _find_external_urls(self, data: dict, path: str = "") -> list[str]:
        """Recursively find external URLs in nested dict."""
        urls = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    if value.startswith(('http://', 'https://')):
                        urls.append(value)
                else:
                    urls.extend(self._find_external_urls(value, f"{path}.{key}"))
        elif isinstance(data, list):
            for item in data:
                urls.extend(self._find_external_urls(item, path))
        
        return urls
    
    def _extract_service_name_from_url(self, url: str) -> str:
        """Extract service name from URL."""
        # Remove protocol
        clean = url.replace('https://', '').replace('http://', '')
        # Get domain
        domain = clean.split('/')[0]
        # Get main part
        parts = domain.split('.')
        if len(parts) >= 2:
            return parts[-2].title()
        return domain
    
    def _generate_system_purpose(self) -> str:
        """Generate 1-sentence system purpose using LLM."""
        if not self.llm_manager:
            return "Purpose not available (LLM not configured)"
        
        # Read README for context
        readme = self.repo_path / "README.md"
        context = ""
        
        if readme.exists():
            try:
                with open(readme) as f:
                    context = f.read(1000)  # First 1000 chars
            except Exception:
                pass
        
        # Fallback: use directory structure
        if not context:
            dirs = [d.name for d in self.repo_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            context = f"Repository structure: {', '.join(dirs[:10])}"
        
        prompt = f"""Describe the system purpose in ONE sentence.

Repository info:
{context}

Answer format: "This system [does something]."

Your answer:"""
        
        try:
            response = self.llm_manager.generate_text(
                prompt,
                max_tokens=40,
                temperature=0.2,
                use_cache=True
            )
            
            if response:
                # Clean and validate - remove thinking tokens and extra text
                sentence = response.strip()
                
                # Remove common LLM artifacts
                sentence = re.sub(r'<think>.*?</think>', '', sentence, flags=re.DOTALL)
                sentence = re.sub(r'<.*?>', '', sentence)
                sentence = sentence.strip()
                
                # Find the first actual sentence
                sentences = re.split(r'[.!?]', sentence)
                for s in sentences:
                    s = s.strip()
                    if len(s) > 20 and ('system' in s.lower() or 'is' in s.lower()):
                        # Ensure it ends with period
                        return s + '.' if not s.endswith('.') else s
                
                # Fallback: take first sentence
                if sentences and len(sentences[0]) > 10:
                    return sentences[0].strip() + '.'
                
                return sentence[:200] + '.' if sentence else "Purpose not available"
        
        except Exception as e:
            logger.debug(f"Failed to generate system purpose: {e}")
        
        return "Purpose not available"
    
    def _detect_owner_team(self) -> str:
        """Detect owner team from CODEOWNERS, README, or git contributors.
        
        Looks for:
        - CODEOWNERS file (@team-name)
        - README maintainers section
        - Slack channel mentions (#team-channel)
        - Git top contributors (fallback)
        """
        # Check CODEOWNERS file
        codeowners_paths = [
            self.repo_path / "CODEOWNERS",
            self.repo_path / ".github" / "CODEOWNERS",
            self.repo_path / "docs" / "CODEOWNERS",
        ]
        
        for codeowners_file in codeowners_paths:
            if codeowners_file.exists():
                try:
                    with open(codeowners_file) as f:
                        content = f.read()
                    
                    # Find @team mentions
                    team_pattern = r'@([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)'
                    teams = re.findall(team_pattern, content)
                    
                    if teams:
                        # Return first team
                        return teams[0]
                
                except Exception:
                    pass
        
        # Check README for maintainers or team info
        readme_paths = [
            self.repo_path / "README.md",
            self.repo_path / "README.rst",
            self.repo_path / "README.txt",
        ]
        
        for readme in readme_paths:
            if readme.exists():
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
                            # Clean and validate
                            if len(team_info) < 50:  # Reasonable length
                                return team_info
                
                except Exception:
                    pass
        
        # Fallback: Get top contributors from git and ask LLM to suggest team name
        top_contributors = self._get_top_git_contributors(max_contributors=3)
        if top_contributors and self.llm_manager:
            suggested_team = self._suggest_team_name_from_contributors(top_contributors)
            if suggested_team:
                return suggested_team
        
        # If git contributors found but no LLM, return first contributor email domain
        if top_contributors:
            first_email = top_contributors[0][0]
            # Extract domain from email (e.g., john@team-name.com -> team-name)
            email_match = re.search(r'@([^.]+)', first_email)
            if email_match:
                return email_match.group(1)
        
        return "Unknown"
    
    def _get_top_git_contributors(self, max_contributors: int = 3) -> list[tuple[str, int]]:
        """Get top contributors from git history.
        
        Returns:
            List of tuples (email, commit_count) sorted by commit count
        """
        if not (self.repo_path / ".git").exists():
            return []
        
        try:
            # Run git shortlog to get contributor stats
            result = subprocess.run(
                ['git', 'shortlog', '-sn', '--all'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return []
            
            # Parse output: "  123\tJohn Doe <john@example.com>"
            contributors = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                # Extract commit count and email
                match = re.search(r'\s+(\d+)\s+.+<([^>]+)>', line)
                if match:
                    commit_count = int(match.group(1))
                    email = match.group(2)
                    contributors.append((email, commit_count))
            
            # Sort by commit count (descending) and return top N
            contributors.sort(key=lambda x: x[1], reverse=True)
            return contributors[:max_contributors]
        
        except Exception as e:
            logger.debug(f"Failed to get git contributors: {e}")
            return []
    
    def _suggest_team_name_from_contributors(self, contributors: list[tuple[str, int]]) -> Optional[str]:
        """Use LLM to suggest a team name from contributor emails.
        
        Args:
            contributors: List of (email, commit_count) tuples
            
        Returns:
            Suggested team name or None
        """
        if not self.llm_manager or not contributors:
            return None
        
        # Build contributor list string
        contributor_list = ", ".join([f"{email} ({count} commits)" for email, count in contributors])
        
        prompt = f"""Given these top git contributors to a repository:
{contributor_list}

Suggest a likely team name or owner group name for this repository. 
Consider email domains, naming patterns, and common team structures.

Return ONLY the team name (e.g., "backend-team", "platform-engineering", "data-team"), nothing else.
If uncertain, return the email domain of the top contributor.

Team name:"""
        
        try:
            response = self.llm_manager.generate_text(
                prompt,
                max_tokens=50,
                temperature=0.3,
                use_cache=True
            )
            
            if response:
                # Clean response
                team_name = response.strip().strip('"').strip("'")
                # Remove thinking tokens or extra text
                team_name = re.sub(r'^[^a-zA-Z0-9_-]+', '', team_name)
                team_name = re.sub(r'[^a-zA-Z0-9_-]+$', '', team_name)
                
                if team_name and len(team_name) < 50:
                    return team_name
        
        except Exception as e:
            logger.debug(f"LLM team name suggestion failed: {e}")
        
        return None
    
    def _infer_business_domain(self) -> str:
        """Infer business domain from repository indicators.
        
        Domains:
        - Infrastructure: K8s, Docker, networking, deployment
        - AI/ML Processing: ML models, training, pipelines
        - Data Engineering: ETL, data pipelines, analytics
        - User Management: Auth, users, permissions
        - API Gateway: Routing, ingress, proxies
        - Developer Tools: CI/CD, testing, monitoring
        """
        # Analyze project structure and dependencies
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
        
        # Check for specific service patterns in containers (generic keywords)
        for container_name in self.containers.keys():
            name_lower = container_name.lower()
            
            # AI/ML keywords
            if any(k in name_lower for k in ['ml', 'model', 'train', 'pipeline', 'job', 'worker', 'clearml', 'kubeflow', 'mlflow', 'mlops', 'sagemaker']):
                indicators['ai_ml'] += 2
            
            # Gateway keywords
            if any(k in name_lower for k in ['gateway', 'proxy', 'router', 'ingress', 'api', 'apisix', 'kong', 'nginx']):
                indicators['api_gateway'] += 2
            
            # Infrastructure keywords
            if any(k in name_lower for k in ['harbor', 'registry', 'vault', 'consul', 'etcd', 'monitoring', 'logging', 'tracing']):
                indicators['infrastructure'] += 2
            
            # Data keywords
            if any(k in name_lower for k in ['data', 'warehouse', 'lake', 'etl', 'analytics', 'kafka', 'spark', 'airflow']):
                indicators['data_engineering'] += 2
            
            # Auth keywords
            if any(k in name_lower for k in ['auth', 'iam', 'identity', 'user', 'account', 'login', 'sso']):
                indicators['user_management'] += 2
        
        # Return domain with highest score
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
    
    def _determine_criticality(self) -> str:
        """Determine system criticality tier.
        
        Tiers:
        - Tier 1: Production-critical (SLA, monitoring, HA)
        - Tier 2: Production-standard (monitoring, backups)
        - Tier 3: Development/Internal (no SLA)
        """
        criticality_score = 0
        
        # Check for production indicators
        prod_indicators = [
            'prod', 'production', 'live', 'master', 'main',
            'sla', 'uptime', 'ha', 'high-availability',
            'monitoring', 'alerting', 'pagerduty',
        ]
        
        # Check namespace in Kubernetes (prod namespace = critical)
        for container in self.containers.values():
            if 'path' in container:
                path_text = container['path'].lower()
                if any(ind in path_text for ind in prod_indicators):
                    criticality_score += 2
        
        # Check values.yaml files for production config
        for values_file in self.repo_path.rglob("values.yaml"):
            try:
                with open(values_file) as f:
                    content = f.read().lower()
                
                # Production indicators
                if 'production' in content or 'prod' in content:
                    criticality_score += 2
                
                # High availability indicators
                if 'replicas: 3' in content or 'replicas: 5' in content:
                    criticality_score += 1
                
                # Resource limits (production systems have limits)
                if 'resources:' in content and 'limits:' in content:
                    criticality_score += 1
                
                # Monitoring/alerting
                if 'prometheus' in content or 'grafana' in content or 'alert' in content:
                    criticality_score += 1
            
            except Exception:
                continue
        
        # Check README for SLA or criticality mentions
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
        
        # Check for CI/CD presence (indicates maintained system)
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
    
    def _extract_level2_containers(self):
        """Extract Level 2: Containers (Deployable Units).
        
        Identifies:
        - Services (from projects/ or services/)
        - Databases (from docker-compose or K8s)
        - Frontends (React, Vue, Angular apps)
        - Workers/Jobs
        """
        # Detect from project structure
        self._detect_containers_from_structure()
        
        # Detect from docker-compose
        self._detect_containers_from_compose()
        
        # Detect from Helm charts
        self._detect_containers_from_helm()
        
        # Infer communication protocols
        self._infer_communication_protocols()
    
    def _detect_containers_from_structure(self):
        """Detect containers from repository structure using recursive search.
        
        Recursively searches for framework manifests (Dockerfile, package.json, etc.)
        to identify deployable services. Works with any repository structure:
        - Monorepos (any directory structure)
        - Single service repos
        - Nested structures
        - Custom layouts
        """
        # Excluded directories (not services)
        excluded_dirs = {
            '__pycache__', '.git', '.github', '.gitlab', 'node_modules',
            'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
            '.idea', '.vscode', 'logs', 'temp', 'tmp', '.pytest_cache',
            'test', 'tests', '__tests__', 'docs', 'documentation',
            '.next', '.nuxt', '.cache', 'coverage', '.coverage',
        }
        
        # Track directories we've already registered
        registered_paths = set()
        
        # Recursively search for framework manifests
        for manifest_file in self.repo_path.rglob("*"):
            if not manifest_file.is_file():
                continue
            
            # Check if this is a framework manifest
            if manifest_file.name not in self.framework_manifests:
                continue
            
            # Get the directory containing this manifest
            service_dir = manifest_file.parent
            
            # Skip if in excluded directory
            if any(excluded in service_dir.parts for excluded in excluded_dirs):
                continue
            
            # Skip if already registered
            rel_path = service_dir.relative_to(self.repo_path)
            if str(rel_path) in registered_paths:
                continue
            
            # Check if this directory looks like a deployable service
            if self._is_deployable_service(service_dir):
                self._register_container(service_dir)
                registered_paths.add(str(rel_path))
        
        # Fallback: If no containers found, check if root is a service
        if not self.containers:
            if self._is_deployable_service(self.repo_path):
                self._register_container(self.repo_path)
    
    def _is_deployable_service(self, directory: Path) -> bool:
        """Check if directory contains a deployable service.
        
        Checks for framework manifest files that indicate a deployable unit.
        """
        # Check for any framework manifest
        for manifest in self.framework_manifests:
            manifest_path = directory / manifest
            if manifest_path.exists():
                return True
        
        # Also check for chart subdirectory (Helm)
        if (directory / "chart" / "Chart.yaml").exists():
            return True
        
        return False
    
    def _register_container(self, project_dir: Path):
        """Register a container (generic method).
        
        Args:
            project_dir: Path to container directory (absolute or relative)
        """
        # Ensure absolute path
        project_dir = Path(project_dir).resolve()
        
        # Get relative path from repo root (standardized)
        rel_path = project_dir.relative_to(self.repo_path)
        rel_path_str = str(rel_path) if rel_path != Path('.') else "."
        
        # Generate container name
        container_name = project_dir.name if project_dir != self.repo_path else self.repo_path.name
        
        # Avoid duplicates (check by relative path)
        for existing_container in self.containers.values():
            if existing_container.get('path') == rel_path_str:
                return
        
        # Filter out non-service directories
        excluded_dirs = {
            '__pycache__', '.git', '.github', '.gitlab', 'node_modules',
            'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
            '.idea', '.vscode', 'logs', 'temp', 'tmp', '.pytest_cache',
            'test', 'tests', '__tests__', 'docs', 'documentation'
        }
        
        if container_name.lower() in excluded_dirs or container_name.startswith('.'):
            return
        
        container_type = self._infer_container_type(project_dir)
        protocol = self._infer_protocol(project_dir)
        
        self.containers[container_name] = {
            "c4_level": 2,
            "type": "container",
            "name": container_name,
            "container_type": container_type,
            "technology": self._detect_technology_stack(project_dir),
            "protocol": protocol,
            "path": rel_path_str,  # Always relative to repo root
            
            # IT Landscape fields
            "repository_url": self._get_repository_url(project_dir),
            "runtime_info": self._extract_runtime_version(project_dir),
            "dependencies_internal": [],  # Will be populated later
            "health_endpoint": self._extract_health_endpoint(project_dir),
        }
    
    def _infer_container_type(self, project_dir: Path) -> str:
        """Infer what type of container this is."""
        # Check for indicators
        if (project_dir / "Dockerfile").exists():
            # Read Dockerfile to guess type
            try:
                with open(project_dir / "Dockerfile") as f:
                    content = f.read().lower()
                    
                    if 'node' in content or 'npm' in content:
                        return "Frontend (Node.js)"
                    elif 'python' in content:
                        if 'fastapi' in content or 'flask' in content:
                            return "Backend API"
                        else:
                            return "Python Service"
                    elif 'java' in content:
                        return "Java Service"
                    elif 'go' in content:
                        return "Go Service"
                    
                    return "Containerized Service"
            except Exception:
                pass
        
        # Check for frontend indicators
        if (project_dir / "package.json").exists():
            try:
                with open(project_dir / "package.json") as f:
                    data = json.load(f)
                    deps = str(data.get('dependencies', {}))
                    
                    if 'react' in deps:
                        return "React Frontend"
                    elif 'vue' in deps:
                        return "Vue Frontend"
                    elif 'angular' in deps:
                        return "Angular Frontend"
                    elif 'express' in deps:
                        return "Node.js Backend"
                    
                    return "JavaScript Application"
            except Exception:
                pass
        
        # Check for backend indicators
        if (project_dir / "pyproject.toml").exists():
            return "Python Service"
        
        # Check for database
        if 'db' in project_dir.name.lower() or 'database' in project_dir.name.lower():
            return "Database"
        
        # Check for worker/job
        if any(keyword in project_dir.name.lower() for keyword in ['worker', 'job', 'queue', 'task']):
            return "Background Worker"
        
        return "Service"
    
    def _detect_technology_stack(self, project_dir: Path) -> str:
        """Detect primary technology stack."""
        if (project_dir / "package.json").exists():
            return "Node.js"
        elif (project_dir / "pyproject.toml").exists():
            return "Python"
        elif (project_dir / "pom.xml").exists():
            return "Java"
        elif (project_dir / "go.mod").exists():
            return "Go"
        elif (project_dir / "Cargo.toml").exists():
            return "Rust"
        
        return "Unknown"
    
    def _infer_protocol(self, project_dir: Path) -> str:
        """Infer communication protocol."""
        # Search for protocol indicators in source files
        protocols = set()
        
        # Check Python files
        for py_file in project_dir.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read(5000)  # First 5000 chars
                    
                    if 'grpc' in content.lower():
                        protocols.add('gRPC')
                    if 'graphql' in content.lower():
                        protocols.add('GraphQL')
                    if '@router' in content or '@app.get' in content or 'fastapi' in content.lower():
                        protocols.add('REST')
                    if 'websocket' in content.lower():
                        protocols.add('WebSocket')
            except Exception:
                continue
            
            if protocols:
                break  # Found something, no need to scan more
        
        # Check JavaScript files
        for js_file in project_dir.rglob("*.js"):
            try:
                with open(js_file) as f:
                    content = f.read(5000)
                    
                    if 'apollo' in content.lower() or 'graphql' in content.lower():
                        protocols.add('GraphQL')
                    if 'express' in content.lower() or 'app.get' in content:
                        protocols.add('REST')
                    if 'grpc' in content.lower():
                        protocols.add('gRPC')
            except Exception:
                continue
            
            if protocols:
                break
        
        if protocols:
            return ', '.join(sorted(protocols))
        
        return "HTTP"  # Default
    
    def _detect_containers_from_compose(self):
        """Detect containers from docker-compose files."""
        compose_files = list(self.repo_path.glob("docker-compose*.yaml")) + \
                       list(self.repo_path.glob("docker-compose*.yml"))
        
        for compose_file in compose_files:
            try:
                with open(compose_file) as f:
                    data = yaml.safe_load(f)
                
                services = data.get('services', {})
                
                for service_name, service_config in services.items():
                    if service_name not in self.containers:
                        # Extract runtime from image
                        image = service_config.get('image', '')
                        runtime = self._extract_runtime_from_image(image)
                        
                        self.containers[service_name] = {
                            "c4_level": 2,
                            "type": "container",
                            "name": service_name,
                            "container_type": self._infer_type_from_image(image),
                            "technology": image.split(':')[0] if image else "Unknown",
                            "protocol": "HTTP",
                            "path": str(compose_file.relative_to(self.repo_path)),
                            
                            # IT Landscape fields
                            "repository_url": self._get_repository_url(compose_file.parent),
                            "runtime_info": runtime,
                            "dependencies_internal": service_config.get('depends_on', []) if isinstance(service_config.get('depends_on'), list) else [],
                            "health_endpoint": self._extract_health_from_compose(service_config),
                        }
            
            except Exception as e:
                logger.debug(f"Error parsing {compose_file}: {e}")
    
    def _detect_containers_from_helm(self):
        """Detect containers from Helm charts."""
        chart_files = list(self.repo_path.rglob("Chart.yaml"))
        
        for chart_file in chart_files:
            try:
                with open(chart_file) as f:
                    data = yaml.safe_load(f)
                
                chart_name = data.get('name', chart_file.parent.name)
                chart_dir = chart_file.parent
                
                if chart_name not in self.containers:
                    self.containers[chart_name] = {
                        "c4_level": 2,
                        "type": "container",
                        "name": chart_name,
                        "container_type": "Helm Deployed Service",
                        "technology": "Kubernetes",
                        "protocol": "HTTP",
                        "path": str(chart_file.relative_to(self.repo_path)),
                        
                        # IT Landscape fields
                        "repository_url": self._get_repository_url(chart_dir),
                        "runtime_info": self._extract_runtime_version(chart_dir),
                        "dependencies_internal": [],
                        "health_endpoint": self._extract_health_endpoint(chart_dir),
                    }
            
            except Exception as e:
                logger.debug(f"Error parsing {chart_file}: {e}")
    
    def _infer_type_from_image(self, image: str) -> str:
        """Infer container type from Docker image name."""
        image_lower = image.lower()
        
        if 'postgres' in image_lower:
            return "PostgreSQL Database"
        elif 'mongo' in image_lower:
            return "MongoDB Database"
        elif 'redis' in image_lower:
            return "Redis Cache"
        elif 'nginx' in image_lower:
            return "Web Server"
        elif 'node' in image_lower:
            return "Node.js Service"
        elif 'python' in image_lower:
            return "Python Service"
        
        return "Service"
    
    def _extract_runtime_from_image(self, image: str) -> str:
        """Extract runtime version from Docker image tag.
        
        Examples:
        - python:3.10 -> Python 3.10
        - node:20-alpine -> Node.js 20
        - openjdk:11 -> Java 11
        """
        if not image or ':' not in image:
            return "Unknown"
        
        try:
            base, tag = image.split(':', 1)
            base_name = base.split('/')[-1]  # Handle registry prefix
            
            # Extract version number from tag
            version_match = re.search(r'(\d+\.?\d*)', tag)
            if version_match:
                version = version_match.group(1)
                
                if 'python' in base_name:
                    return f"Python {version}"
                elif 'node' in base_name:
                    return f"Node.js {version}"
                elif 'java' in base_name or 'openjdk' in base_name:
                    return f"Java {version}"
                elif 'go' in base_name or 'golang' in base_name:
                    return f"Go {version}"
                elif 'postgres' in base_name:
                    return f"PostgreSQL {version}"
                elif 'mongo' in base_name:
                    return f"MongoDB {version}"
                elif 'redis' in base_name:
                    return f"Redis {version}"
                else:
                    return f"{base_name.title()} {version}"
        
        except Exception:
            pass
        
        return "Unknown"
    
    def _extract_health_from_compose(self, service_config: dict) -> str:
        """Extract health check endpoint from docker-compose service config."""
        # Check for healthcheck
        if 'healthcheck' in service_config:
            healthcheck = service_config['healthcheck']
            if 'test' in healthcheck:
                test = healthcheck['test']
                # Parse health check command
                if isinstance(test, list):
                    test_cmd = ' '.join(test)
                elif isinstance(test, str):
                    test_cmd = test
                else:
                    return ""
                
                # Extract URL from curl/wget commands
                url_match = re.search(r'https?://[^\s]+', test_cmd)
                if url_match:
                    return url_match.group(0)
                
                # Extract path
                path_match = re.search(r'/[\w/-]+', test_cmd)
                if path_match:
                    return f"http://localhost{path_match.group(0)}"
        
        return ""
    
    def _infer_communication_protocols(self):
        """Infer communication protocols for containers."""
        # Already done inline in detection methods
        pass
    
    def _get_repository_url(self, project_dir: Path) -> str:
        """Get GitLab/GitHub URL for this service subfolder.
        
        Constructs URL from git remote and project path.
        """
        try:
            # Get git remote URL
            import subprocess
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                
                # Convert SSH to HTTPS URL
                if remote_url.startswith('git@'):
                    # git@gitlab.com:user/repo.git -> https://gitlab.com/user/repo
                    remote_url = remote_url.replace('git@', 'https://').replace('.com:', '.com/')
                
                # Remove .git suffix
                remote_url = remote_url.rstrip('.git')
                
                # Add path to service subfolder
                rel_path = project_dir.relative_to(self.repo_path)
                service_url = f"{remote_url}/-/tree/main/{rel_path}"
                
                return service_url
        
        except Exception as e:
            logger.debug(f"Failed to get repository URL: {e}")
        
        return ""
    
    def _extract_runtime_version(self, project_dir: Path) -> str:
        """Extract runtime version (Python 3.10, Node 20, etc.).
        
        Checks:
        - Dockerfile (FROM python:3.10)
        - pyproject.toml (requires-python = ">=3.10")
        - package.json (engines.node)
        - .python-version, .node-version files
        """
        # Check Dockerfile
        dockerfile = project_dir / "Dockerfile"
        if dockerfile.exists():
            try:
                with open(dockerfile) as f:
                    content = f.read()
                
                # Find FROM statements
                from_pattern = r'FROM\s+([^\s]+)'
                matches = re.findall(from_pattern, content)
                
                for image in matches:
                    # Extract version from image
                    # Examples: python:3.10, node:20, openjdk:11
                    if ':' in image:
                        base, version = image.split(':', 1)
                        
                        if 'python' in base:
                            return f"Python {version}"
                        elif 'node' in base:
                            return f"Node.js {version}"
                        elif 'openjdk' in base or 'java' in base:
                            return f"Java {version}"
                        elif 'golang' in base or 'go' in base:
                            return f"Go {version}"
            
            except Exception:
                pass
        
        # Check pyproject.toml
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'rb') as f:
                    data = tomli.load(f)
                
                # Check requires-python
                requires_python = data.get('project', {}).get('requires-python', '')
                if requires_python:
                    # Extract version number
                    version_match = re.search(r'[\d.]+', requires_python)
                    if version_match:
                        return f"Python {version_match.group()}"
            
            except Exception:
                pass
        
        # Check package.json
        package_json = project_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                
                # Check engines
                engines = data.get('engines', {})
                if 'node' in engines:
                    return f"Node.js {engines['node']}"
            
            except Exception:
                pass
        
        # Check version files
        version_files = {
            '.python-version': 'Python',
            '.node-version': 'Node.js',
            '.ruby-version': 'Ruby',
            '.java-version': 'Java',
        }
        
        for version_file, runtime in version_files.items():
            vfile = project_dir / version_file
            if vfile.exists():
                try:
                    with open(vfile) as f:
                        version = f.read().strip()
                    return f"{runtime} {version}"
                except Exception:
                    pass
        
        return "Unknown"
    
    def _extract_health_endpoint(self, project_dir: Path) -> str:
        """Extract health check endpoint URL.
        
        Looks in:
        - values.yaml (ingress.host + health path)
        - deployment.yaml (liveness/readiness probes)
        - Source code (FastAPI health routes)
        """
        # Check values.yaml for ingress config
        values_file = project_dir / "chart" / "values.yaml"
        if values_file.exists():
            try:
                with open(values_file) as f:
                    data = yaml.safe_load(f)
                
                # Extract host and health path
                host = None
                health_path = "/health"
                
                # Look for ingress host
                if 'ingress' in data:
                    ingress = data['ingress']
                    if 'host' in ingress:
                        host = ingress['host']
                    elif 'hosts' in ingress and ingress['hosts']:
                        host = ingress['hosts'][0] if isinstance(ingress['hosts'], list) else ingress['hosts'].get('host')
                
                # Look for health check path
                if 'health' in data:
                    health_config = data['health']
                    if 'path' in health_config:
                        health_path = health_config['path']
                
                # Look for service config
                if 'service' in data:
                    service = data['service']
                    if 'port' in service:
                        port = service['port']
                        if host:
                            return f"https://{host}{health_path}"
                
                if host:
                    return f"https://{host}{health_path}"
            
            except Exception:
                pass
        
        # Check deployment.yaml for readiness probe
        for deployment_file in project_dir.rglob("deployment.yaml"):
            try:
                with open(deployment_file) as f:
                    content = f.read()
                
                # Look for httpGet path in readiness/liveness probe
                probe_pattern = r'(?:readinessProbe|livenessProbe):\s*httpGet:\s*path:\s*([^\s]+)'
                match = re.search(probe_pattern, content)
                
                if match:
                    health_path = match.group(1)
                    return f"http://localhost:8080{health_path}"
            
            except Exception:
                pass
        
        return ""
    
    def _map_internal_dependencies(self):
        """Map dependencies between containers (creates the connection lines).
        
        Analyzes:
        - values.yaml (service URLs, endpoints)
        - Source code (HTTP calls to other services)
        - Environment variables (service discovery)
        """
        for container_name, container_info in self.containers.items():
            dependencies = set()
            container_path = self.repo_path / container_info['path']
            
            # Check values.yaml for service references
            values_file = container_path / "chart" / "values.yaml"
            if values_file.exists():
                try:
                    with open(values_file) as f:
                        content = f.read()
                    
                    # Look for other container names in the config
                    for other_container in self.containers.keys():
                        if other_container != container_name:
                            # Check if other service is referenced
                            if other_container in content:
                                dependencies.add(other_container)
                
                except Exception:
                    pass
            
            # Check source code for HTTP calls
            for py_file in container_path.rglob("*.py"):
                try:
                    with open(py_file) as f:
                        content = f.read()
                    
                    # Look for requests to other services
                    # Pattern: requests.post(f"http://{service_name}")
                    for other_container in self.containers.keys():
                        if other_container != container_name:
                            if other_container in content.lower():
                                dependencies.add(other_container)
                
                except Exception:
                    continue
            
            # Update container with dependencies
            container_info['dependencies_internal'] = sorted(list(dependencies))
    
    def _extract_level3_components(self):
        """Extract Level 3: Components (Public Entry Points Only).
        
        Scans for:
        - @Controller, @RestController (Java/Spring)
        - @router.get, @app.post (Python/FastAPI)
        - export function handler (JavaScript/Node)
        
        IGNORES:
        - Private methods
        - Helper functions
        - Internal classes
        
        Generic approach: Scans entire repository, adapts to any structure.
        """
        # Scan from repository root (works for any structure)
        components = self._scan_for_entry_points(self.repo_path, "root")
        
        for comp in components:
            comp_id = f"{comp['container']}::{comp['name']}"
            self.components[comp_id] = comp
    
    def _scan_for_entry_points(self, directory: Path, container_name: str) -> list[dict[str, Any]]:
        """Scan for public entry points (APIs, controllers, routes).
        
        Uses language detectors (Strategy Pattern) for extensible detection.
        """
        entry_points = []
        
        # Excluded directories
        excluded_dirs = {'node_modules', 'test', 'tests', '__tests__', '__pycache__', '.git'}
        
        # Use language detectors to scan files
        for detector in self.language_detectors:
            # Get file extensions for this detector
            extensions = detector.get_file_extensions()
            
            # Scan files with matching extensions
            for ext in extensions:
                pattern = f"*{ext}"
                for file_path in directory.rglob(pattern):
                    # Skip excluded directories
                    if any(excluded in file_path.parts for excluded in excluded_dirs):
                        continue
                    
                    # Skip private/internal files
                    if file_path.name.startswith('_') and file_path.name != '__init__.py':
                        continue
                    
                    try:
                        with open(file_path, encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Use detector to extract entry points
                        detected_points = detector.extract_entry_points(file_path, content)
                        
                        for point in detected_points:
                            # Infer container from path structure
                            inferred_container = self._infer_container_from_path(file_path)
                            
                            # Get relative path (standardized)
                            rel_path = file_path.relative_to(self.repo_path)
                            
                            # Build component entry
                            component = {
                                "c4_level": 3,
                                "type": "component",
                                "component_type": "API Endpoint",
                                "container": inferred_container or container_name,
                                "file": str(rel_path),  # Always relative to repo root
                            }
                            
                            # Add method and path if available
                            if point.get('method') and point.get('path'):
                                component.update({
                                    "name": f"{point['method']} {point['path']}",
                                    "function_name": point.get('name', 'unknown'),
                                    "endpoint_path": point['path'],
                                    "endpoint_method": point['method'],
                                })
                                
                                # Extract additional metadata (Python-specific for now)
                                if ext == '.py':
                                    api_visibility = self._determine_api_visibility(
                                        point['path'], file_path
                                    )
                                    data_models = self._extract_data_models(
                                        content, point.get('name', ''), point['method']
                                    )
                                    component.update({
                                        "api_visibility": api_visibility,
                                        "data_model": data_models,
                                    })
                            else:
                                # Controller class or other entry point without specific route
                                component.update({
                                    "name": point.get('name', 'unknown'),
                                    "function_name": point.get('name', 'unknown'),
                                })
                            
                            entry_points.append(component)
                    
                    except Exception as e:
                        logger.debug(f"Error scanning {file_path}: {e}")
        
        return entry_points
    
    def _infer_container_from_path(self, file_path: Path) -> Optional[str]:
        """Infer container name from file path (generic).
        
        Works with any repository structure:
        - Monorepo: projects/service_name/... → service_name
        - Single service: src/api.py → repo_name
        - Custom: any/path/... → finds closest container
        """
        try:
            rel_path = file_path.relative_to(self.repo_path)
            parts = rel_path.parts
            
            # Strategy 1: Check if file is under a known container
            for container_name, container_info in self.containers.items():
                container_path = container_info.get('path', '')
                if container_path and container_path != '.':
                    # Check if file is under this container's path
                    if str(rel_path).startswith(container_path):
                        return container_name
            
            # Strategy 2: Walk up directory tree to find closest container
            # Look for directories with framework manifests
            current = file_path.parent
            max_depth = 5  # Prevent infinite loops
            depth = 0
            
            while (current != self.repo_path and 
                   current.parent != self.repo_path.parent and 
                   depth < max_depth):
                if self._is_deployable_service(current):
                    return current.name
                current = current.parent
                depth += 1
            
            # Strategy 3: Fallback to first directory level
            if len(parts) >= 1:
                return parts[0]
            
            return None
        
        except Exception:
            return None
    
    def _determine_api_visibility(self, endpoint_path: str, file_path: Path) -> str:
        """Determine if API endpoint is internal or external.
        
        Rules:
        - External: Public-facing APIs (no /internal prefix, documented)
        - Internal: Backend-to-backend, /internal prefix, or private paths
        """
        # Check path patterns
        path_lower = endpoint_path.lower()
        
        # Internal indicators
        if any(prefix in path_lower for prefix in ['/internal', '/private', '/admin', '/_']):
            return "internal"
        
        # Health/metrics endpoints are usually internal
        if any(keyword in path_lower for keyword in ['/health', '/metrics', '/status', '/readiness', '/liveness']):
            return "internal"
        
        # Check file location
        file_parts = str(file_path).lower()
        if 'internal' in file_parts or 'private' in file_parts:
            return "internal"
        
        # Check for authentication requirements (usually external if auth required)
        # This is a heuristic - external APIs often have auth
        if any(keyword in path_lower for keyword in ['/api/v', '/v1/', '/v2/', '/public']):
            return "external"
        
        # Default: internal (safer assumption)
        return "internal"
    
    def _extract_data_models(self, content: str, func_name: str, method: str) -> dict[str, Any]:
        """Extract Request/Response data models from function signature.
        
        Uses LLM to analyze function and extract schemas.
        Returns request and response model information.
        """
        # Find the function definition and a few lines around it
        func_pattern = rf'def\s+{func_name}\s*\([^)]*\).*?(?=\n(?:def|class|@|\Z))'
        func_match = re.search(func_pattern, content, re.DOTALL)
        
        if not func_match:
            return {"request": None, "response": None}
        
        func_code = func_match.group(0)[:1000]  # Limit to first 1000 chars
        
        # Quick regex extraction first (fast path)
        request_model = self._extract_request_model_regex(func_code)
        response_model = self._extract_response_model_regex(func_code)
        
        # If LLM available and we need more details, use it
        if self.llm_manager and (not request_model or not response_model):
            llm_models = self._extract_models_with_llm(func_code, func_name, method)
            if llm_models:
                request_model = request_model or llm_models.get('request')
                response_model = response_model or llm_models.get('response')
        
        return {
            "request": request_model,
            "response": response_model
        }
    
    def _extract_request_model_regex(self, func_code: str) -> Optional[dict[str, Any]]:
        """Extract request model using regex (fast path)."""
        # Look for type hints in function parameters
        # Pattern: def func(param: RequestModel, ...)
        param_pattern = r'(\w+):\s*(\w+(?:Request|Body|Input|Schema|Model))'
        matches = re.findall(param_pattern, func_code)
        
        if matches:
            param_name, model_name = matches[0]
            return {
                "model_name": model_name,
                "param_name": param_name,
                "fields": []  # Would need deeper analysis
            }
        
        return None
    
    def _extract_response_model_regex(self, func_code: str) -> Optional[dict[str, Any]]:
        """Extract response model using regex (fast path)."""
        # Look for return type annotation
        # Pattern: -> ResponseModel
        return_pattern = r'->\s*(\w+(?:Response|Output|Result|Schema|Model))'
        match = re.search(return_pattern, func_code)
        
        if match:
            model_name = match.group(1)
            return {
                "model_name": model_name,
                "fields": []  # Would need deeper analysis
            }
        
        return None
    
    def _extract_models_with_llm(self, func_code: str, func_name: str, method: str) -> Optional[dict[str, Any]]:
        """Extract data models using LLM for detailed analysis."""
        if not self.llm_manager:
            return None
        
        prompt = f"""Analyze this API endpoint function and extract the request and response data models.

Function: {func_name}
Method: {method}
Code:
{func_code[:800]}

Extract:
1. Request model (parameters the client sends)
2. Response model (data the API returns)

Format as JSON:
{{
  "request": {{
    "model_name": "ModelName or null",
    "fields": ["field1", "field2"]
  }},
  "response": {{
    "model_name": "ModelName or null",
    "fields": ["field1", "field2"]
  }}
}}

Answer:"""
        
        try:
            response = self.llm_manager.generate_text(
                prompt,
                max_tokens=200,
                temperature=0.2,
                use_cache=True
            )
            
            if response:
                # Try to extract JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        return data
                    except json.JSONDecodeError:
                        pass
        
        except Exception as e:
            logger.debug(f"LLM model extraction failed: {e}")
        
        return None
    
    def _group_by_domain(self):
        """Group components by domain if too many."""
        # Group by top-level folder
        domains = defaultdict(list)
        
        for comp_id, comp in self.components.items():
            file_path = comp.get('file', '')
            parts = Path(file_path).parts
            
            if len(parts) > 0:
                domain = parts[0]
                domains[domain].append(comp)
        
        # Replace individual components with domain groups
        grouped_components = {}
        
        for domain, comps in domains.items():
            if len(comps) > 3:
                # Create domain group
                grouped_components[domain] = {
                    "c4_level": 3,
                    "type": "component_group",
                    "name": domain,
                    "component_type": "Domain",
                    "component_count": len(comps),
                    "components": [c['name'] for c in comps],
                }
            else:
                # Keep individual components
                for comp in comps:
                    grouped_components[f"{domain}::{comp['name']}"] = comp
        
        self.components = grouped_components
    
    def save(self, c4_data: dict[str, Any], output_path: Path):
        """Save C4 architecture to JSON."""
        with open(output_path, 'w') as f:
            json.dump(c4_data, f, indent=2)
        
        logger.info(f"💾 C4 architecture saved to: {output_path}")
        
        return c4_data


def main():
    """Test C4 extractor."""
    import sys
    
    # Add app-dev to path (go up 3 levels: c4_extractor -> code_extraction -> services -> app-dev)
    app_dev_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(app_dev_path))
    
    from infrastructure.llm.llm_manager import LLMManager
    
    # Path to monorepo (go up 4 more levels to KnowledgeForge)
    monorepo_path = Path(__file__).parent.parent.parent.parent.parent.parent / "monorepo"
    
    if not monorepo_path.exists():
        print(f"❌ Monorepo not found: {monorepo_path}")
        sys.exit(1)
    
    # Initialize LLM (optional)
    try:
        llm = LLMManager(lmstudio_url="http://127.0.0.1:1234")
    except Exception:
        llm = None
        print("⚠️  LLM not available, proceeding without system purpose generation")
    
    # Create extractor
    extractor = C4ArchitectureExtractor(monorepo_path, llm_manager=llm)
    
    # Extract C4 architecture
    c4_architecture = extractor.extract()
    
    # Save
    output_file = app_dev_path / "c4_architecture.json"
    extractor.save(c4_architecture, output_file)
    
    # Print summary
    print("\n" + "="*80)
    print("📊 C4 ARCHITECTURE SUMMARY")
    print("="*80)
    
    print(f"\n📊 Level 1 - System Context:")
    print(f"   System: {c4_architecture['system_context']['name']}")
    print(f"   Owner: {c4_architecture['system_context']['owner_team']}")
    print(f"   Domain: {c4_architecture['system_context']['business_domain']}")
    print(f"   Criticality: {c4_architecture['system_context']['criticality']}")
    print(f"   Purpose: {c4_architecture['system_context']['purpose']}")
    print(f"   External Deps: {len(c4_architecture['system_context']['external_dependencies'])}")
    
    print(f"\n📦 Level 2 - Containers: {len(c4_architecture['containers'])}")
    for container in c4_architecture['containers'][:5]:
        print(f"   • {container['name']:30} ({container['container_type']})")
    if len(c4_architecture['containers']) > 5:
        print(f"   ... and {len(c4_architecture['containers']) - 5} more")
    
    print(f"\n🔌 Level 3 - Components: {len(c4_architecture['components'])}")
    components_list = c4_architecture['components'] if isinstance(c4_architecture['components'], list) else list(c4_architecture['components'].values())
    for comp in components_list[:3]:
        comp_name = comp['name']
        visibility = comp.get('api_visibility', 'unknown')
        vis_icon = "🌐" if visibility == "external" else "🔒"
        
        print(f"   {vis_icon} {comp_name:35} ({visibility})")
        
        # Show data models if available
        data_model = comp.get('data_model', {})
        if data_model:
            req = data_model.get('request')
            resp = data_model.get('response')
            if req and req.get('model_name'):
                print(f"      Request:  {req['model_name']}")
            if resp and resp.get('model_name'):
                print(f"      Response: {resp['model_name']}")
    
    if len(components_list) > 3:
        print(f"   ... and {len(components_list) - 3} more")
    
    print("\n" + "="*80)
    print("✨ C4 Extraction Complete!")
    print("="*80)
    print(f"\nCompare:")
    print(f"  Old approach: 95 entities (overwhelming)")
    print(f"  C4 approach: {len(c4_architecture['containers']) + len(c4_architecture['components'])} architectural elements (manageable)")
    print(f"\n  Reduction: {((95 - (len(c4_architecture['containers']) + len(c4_architecture['components']))) / 95 * 100):.0f}% less noise!")


if __name__ == "__main__":
    main()

