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
from collections import Counter, defaultdict
from abc import ABC, abstractmethod

from app.services.code_extraction.python_ast_extractor import PythonASTExtractor
from app.domain.models.code_entities import CodeEntityType, CodeEntity
from app.services.c4.containers import ContainerManager, is_deployable_service
from app.services.c4.context import ContextManager

import yaml
import tomli

logger = logging.getLogger(__name__)

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
}

FRAMEWORK_INDICATORS: dict[str, tuple[str, str]] = {
    "fastapi": ("Python", "FastAPI"),
    "flask": ("Python", "Flask"),
    "django": ("Python", "Django"),
    "starlette": ("Python", "Starlette"),
    "express": ("JavaScript", "Express"),
    "next": ("TypeScript", "Next.js"),
    "react": ("TypeScript", "React"),
    "vue": ("JavaScript", "Vue.js"),
    "nestjs": ("TypeScript", "NestJS"),
    "@nestjs": ("TypeScript", "NestJS"),
    "gin-gonic": ("Go", "Gin"),
    "echo": ("Go", "Echo"),
    "actix-web": ("Rust", "Actix"),
    "axum": ("Rust", "Axum"),
    "spring": ("Java", "Spring"),
}


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
        self.context_relationships = []
        self.container_relationships = []
        self.cluster_metadata = {}
        
        # Detailed code graph structures
        self.detailed_entities = []
        self.detailed_relationships = []

        # Extractors
        self.ast_extractor = PythonASTExtractor(self.repo_path)
        
        # Container manager for Level 2 detection
        self.container_manager = ContainerManager(self.repo_path, llm_manager)
        
        # Language detectors (Strategy Pattern)
        self.language_detectors = [
            PythonLanguageDetector(),
            JavaScriptLanguageDetector(),
            JavaLanguageDetector(),
        ]
    
    def extract(self, max_components_per_domain: int = 10, group_components_by_domain: bool = False) -> dict[str, Any]:
        """Extract C4 architecture.
        
        Args:
            max_components_per_domain: Group components if more than this
            group_components_by_domain: Enable domain grouping of components
            
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
        
        # Level 1: Context (System + External Dependencies + IT Landscape metadata)
        logger.info("\n📊 LEVEL 1: System Context")
        logger.info("-"*80)
        self._extract_level1_context()
        logger.info(f"✓ System: {self.system_context.get('name', 'Unknown')}")
        logger.info(f"✓ Owner: {self.system_context.get('owner_team', self.system_context.get('owner', 'Unknown'))}")
        logger.info(f"✓ Domain: {self.system_context.get('business_domain', self.system_context.get('domain', 'Unknown'))}")
        logger.info(f"✓ Status: {self.system_context.get('status', 'Unknown')}")
        logger.info(f"✓ Criticality: {self.system_context.get('criticality', self.system_context.get('tier', 'Unknown'))}")
        logger.info(f"✓ Active Experts: {self.system_context.get('active_experts', 'N/A')}")
        logger.info(f"✓ Compliance: {self.system_context.get('compliance', 'Unknown')}")
        logger.info(f"✓ External dependencies: {len(self.system_context.get('external_dependencies', []))}")

        # Build container relationships (context relationships built in _extract_level1_context)
        self.container_relationships = self.container_manager.build_container_relationships()
        self.cluster_metadata = self.container_manager.detect_cluster_metadata()
        
        # Level 4: Detailed Code Graph (AST-based) - MUST RUN BEFORE LEVEL 3
        logger.info("\n🔬 LEVEL 4: Code (Detailed AST Scan)")
        logger.info("-"*80)
        self._extract_level4_code_details()
        logger.info(f"✓ Detailed entities: {len(self.detailed_entities)}")
        logger.info(f"✓ Detailed relationships: {len(self.detailed_relationships)}")
        
        # Level 3: Components (Deep Architectural Scan from code entities)
        logger.info("\n🔌 LEVEL 3: Components")
        logger.info("-"*80)
        self._extract_level3_components()
        logger.info(f"✓ Components: {len(self.components)}")
        
        # Create relationships between components and containers
        self._link_components_to_containers()
        logger.info(f"✓ Component-container links created")
        
        # Level 4 code details already extracted above
        # (Needed for Component extraction)
        
        # Group by domain if too many
        if group_components_by_domain and len(self.components) > max_components_per_domain:
            logger.info(f"✓ Grouping {len(self.components)} components by domain...")
            self._group_by_domain()
        
        # Build final structure
        c4_architecture = {
            "c4_model_version": "1.0",
            "system_context": self.system_context,
            "containers": list(self.containers.values()),
            "components": list(self.components.values()),
            "relationships": {
                "context": self.context_relationships,
                "containers": self.container_relationships,
            },
            "code_level": {
                "entities": [e.model_dump(mode='json') for e in self.detailed_entities],
                "relationships": [r.model_dump(mode='json') for r in self.detailed_relationships],
            },
            "metadata": {
                "total_containers": len(self.containers),
                "total_components": len(self.components),
                "total_code_entities": len(self.detailed_entities),
                "extraction_approach": "c4_model_hybrid",
                "runtime": {
                    "platform": "Kubernetes" if self.cluster_metadata else "Unknown",
                    "cluster": self.cluster_metadata,
                },
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
        """Extract Level 1: System Context using ContextManager.
        
        Uses c4/context module for full Service model field extraction:
        - System name, purpose, external dependencies, actors
        - All 7 primary fields: domain, owner, status, tier, data_class,
          active_experts, compliance
        - Git metrics: commit counts, contributor stats
        """
        context_manager = ContextManager(
            self.repo_path,
            self.llm_manager,
            self.containers,
        )
        self.system_context = context_manager.extract_context()
        self.context_relationships = context_manager.build_context_relationships(
            self.system_context
        )

    def _detect_languages(self) -> list[dict[str, Any]]:
        """Detect primary languages by file extension frequency."""
        ext_counts: Counter[str] = Counter()
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".tox", ".pytest_cache",
        }

        for file_path in self.repo_path.rglob("*"):
            if any(part in skip_dirs for part in file_path.parts):
                continue
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in LANGUAGE_EXTENSIONS:
                    ext_counts[ext] += 1

        languages = []
        for ext, count in ext_counts.most_common():
            languages.append({
                "language": LANGUAGE_EXTENSIONS[ext],
                "file_count": count,
            })

        return languages

    def _detect_frameworks(self) -> list[dict[str, Any]]:
        """Detect frameworks from manifest files."""
        frameworks: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_framework(language: str, framework: str, source: str):
            key = (language, framework)
            if key in seen:
                return
            frameworks.append({
                "language": language,
                "framework": framework,
                "detected_from": source,
            })
            seen.add(key)

        manifest_names = {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Pipfile",
            "setup.py",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "go.mod",
            "Cargo.toml",
        }

        for manifest in self.repo_path.rglob("*"):
            if not manifest.is_file():
                continue
            if manifest.name not in manifest_names:
                continue

            rel_path = str(manifest.relative_to(self.repo_path))
            try:
                if manifest.name == "package.json":
                    data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    dep_text = " ".join(deps.keys()).lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in dep_text:
                            add_framework(lang, fw, rel_path)
                else:
                    content = manifest.read_text(encoding="utf-8", errors="ignore").lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in content:
                            add_framework(lang, fw, rel_path)
            except Exception:
                continue

        return frameworks

    def _detect_context_actors(self) -> list[dict[str, Any]]:
        """Detect human/system actors for Context diagram.

        Heuristics based on README/docs headings and common role keywords.
        """
        actor_candidates = set()
        role_keywords = {
            'user': 'User',
            'admin': 'Administrator',
            'operator': 'Operator',
            'developer': 'Developer',
            'engineer': 'Engineer',
            'client': 'API Client',
            'customer': 'Customer',
            'analyst': 'Analyst',
        }

        candidate_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        candidate_files.extend(self.repo_path.rglob("docs/*.md"))
        candidate_files.extend(self.repo_path.rglob("documentation/*.md"))

        for doc in candidate_files:
            try:
                with open(doc, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_lower = line.lower()
                        # Prefer headings for roles/personas
                        if line.strip().startswith('#'):
                            for key, label in role_keywords.items():
                                if key in line_lower:
                                    actor_candidates.add(label)
                        # Catch inline mentions of CLI or SDK usage
                        if 'cli' in line_lower:
                            actor_candidates.add('CLI User')
                        if 'sdk' in line_lower or 'api client' in line_lower:
                            actor_candidates.add('API Client')
            except Exception:
                continue

        if not actor_candidates:
            actor_candidates.add('User')

        return [{"name": name, "type": "person"} for name in sorted(actor_candidates)]

    def _build_context_relationships(self) -> list[dict[str, Any]]:
        """Build relationships for the Context diagram (actors + external systems)."""
        relationships = []
        system_name = self.system_context.get('name', self.repo_path.name)

        # Actor -> System relationships
        for actor in self.system_context.get('actors', []):
            relationships.append({
                "source": actor.get('name', 'User'),
                "destination": system_name,
                "description": "uses",
                "relationship_type": "uses",
            })

        # System -> External dependency relationships
        for dep in self.system_context.get('external_dependencies', []):
            dep_name = dep.get('name') or dep.get('service') or 'External Service'
            dep_type = dep.get('type') or dep.get('category') or 'external'
            relationships.append({
                "source": system_name,
                "destination": dep_name,
                "description": f"uses {dep_type}",
                "relationship_type": "uses",
            })

        return relationships
    
    def _detect_system_name(self) -> str:
        """Detect system name from project files or use LLM."""
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
        readme_title = None
        readme_content = None
        if readme.exists():
            try:
                with open(readme, 'r', encoding='utf-8') as f:
                    readme_content = f.read(500)  # First 500 chars
                    lines = readme_content.split('\n')
                    first_line = lines[0].strip() if lines else ''
                    # Extract from # Title
                    if first_line.startswith('#'):
                        readme_title = first_line.lstrip('#').strip()
                        if readme_title and not any(word in readme_title.lower() for word in ['readme', 'documentation', 'docs']):
                            return readme_title
            except Exception:
                pass
        
        # Use LLM to generate a better project name if available
        if self.llm_manager and readme_content:
            try:
                repo_url = self._get_repository_root_url()
                dir_name = self.repo_path.name
                
                prompt = f"""Based on this README excerpt, suggest a short, descriptive project name (2-4 words max).

README:
{readme_content[:300]}

Repository name: {dir_name}
{f"Repository URL: {repo_url}" if repo_url else ""}

Respond with ONLY the project name, nothing else.
Example good names: "Payment Processing Service", "User Auth API", "ML Training Pipeline"

Your answer:"""
                
                response = self.llm_manager.generate_text(
                    prompt,
                    max_tokens=20,
                    temperature=0.3,
                    use_cache=True
                )
                
                if response:
                    # Clean up LLM response
                    project_name = response.strip()
                    project_name = re.sub(r'<[^>]+>', '', project_name)  # Remove XML tags
                    project_name = project_name.strip('"\'')  # Remove quotes
                    
                    # Validate: should be reasonable length and not contain weird chars
                    if 5 <= len(project_name) <= 60 and not any(char in project_name for char in ['<', '>', '{', '}', '[', ']']):
                        return project_name
            except Exception as e:
                logger.debug(f"Failed to generate project name with LLM: {e}")
        
        # Fallback: clean up directory name
        dir_name = self.repo_path.name
        # Convert common patterns: my-project -> My Project
        cleaned_name = dir_name.replace('-', ' ').replace('_', ' ').title()
        return cleaned_name if len(cleaned_name) > 3 else dir_name

    def _get_repository_root_url(self) -> str:
        """Get repository URL from git remote origin."""
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return ""

            remote_url = result.stdout.strip()
            if not remote_url:
                return ""

            if remote_url.startswith("git@"):
                remote_url = remote_url.replace("git@", "https://").replace(".com:", ".com/")
            remote_url = remote_url.rstrip(".git")
            return remote_url
        except Exception:
            return ""

    def _extract_git_metadata(self) -> dict[str, Any]:
        """Extract git metadata for manager-level context."""
        if not (self.repo_path / ".git").exists():
            return {}

        def run_git(args: list[str]) -> str:
            try:
                result = subprocess.run(
                    args,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                return ""
            return ""

        metadata: dict[str, Any] = {}

        branch = run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if branch:
            metadata["branch"] = branch

        commit_hash = run_git(["git", "rev-parse", "HEAD"])
        if commit_hash:
            metadata["commit_hash"] = commit_hash

        last_commit_date = run_git(["git", "log", "-1", "--format=%cI"])
        if last_commit_date:
            metadata["last_commit_date"] = last_commit_date

        first_commit_date = run_git(["git", "log", "--reverse", "--format=%cI", "-n", "1"])
        if first_commit_date:
            metadata["first_commit_date"] = first_commit_date

        total_commits = run_git(["git", "rev-list", "--count", "HEAD"])
        if total_commits.isdigit():
            metadata["total_commits"] = int(total_commits)

        def count_since(days: int) -> int:
            log = run_git(["git", "log", f"--since={days}.days", "--oneline"])
            if not log:
                return 0
            return sum(1 for line in log.splitlines() if line.strip())

        metadata["commits_30d"] = count_since(30)
        metadata["commits_90d"] = count_since(90)
        metadata["commits_180d"] = count_since(180)

        tags = run_git(["git", "tag", "--sort=-creatordate"])
        if tags:
            tag_list = [tag for tag in tags.splitlines() if tag.strip()]
            metadata["tag_count"] = len(tag_list)
            metadata["latest_tag"] = tag_list[0] if tag_list else None

        shortlog = run_git(["git", "shortlog", "-sn", "--all"])
        contributors = []
        if shortlog:
            for line in shortlog.splitlines()[:5]:
                match = re.match(r"\s*(\d+)\s+(.+?)\s+<([^>]+)>", line)
                if match:
                    contributors.append({
                        "name": match.group(2).strip(),
                        "email": match.group(3).strip(),
                        "commit_count": int(match.group(1)),
                    })
                else:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        contributors.append({
                            "name": parts[1].strip(),
                            "email": "",
                            "commit_count": int(parts[0]),
                        })

        if contributors:
            metadata["top_contributors"] = contributors

        return metadata

    def _collect_context_sources(self, frameworks: list[dict[str, Any]]) -> dict[str, Any]:
        """Collect key files used for context extraction."""
        sources: dict[str, Any] = {}

        readme_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                readme_files.append(str(path.relative_to(self.repo_path)))

        for doc in list(self.repo_path.rglob("docs/*.md"))[:5]:
            readme_files.append(str(doc.relative_to(self.repo_path)))
        for doc in list(self.repo_path.rglob("documentation/*.md"))[:5]:
            readme_files.append(str(doc.relative_to(self.repo_path)))

        if readme_files:
            sources["readme_files"] = readme_files[:8]

        deployment_files = []
        for dockerfile in self.repo_path.rglob("Dockerfile"):
            deployment_files.append(str(dockerfile.relative_to(self.repo_path)))
        for compose_file in self.repo_path.rglob("docker-compose*.y*ml"):
            deployment_files.append(str(compose_file.relative_to(self.repo_path)))
        deployment_files.extend(self._find_k8s_manifest_files(limit=8))

        if deployment_files:
            sources["deployment_files"] = deployment_files[:10]

        framework_files = sorted({
            fw.get("detected_from")
            for fw in frameworks
            if fw.get("detected_from")
        })
        if framework_files:
            sources["framework_files"] = framework_files[:10]

        return sources

    def _find_k8s_manifest_files(self, limit: int = 10) -> list[str]:
        """Find Kubernetes manifest files for context sources."""
        matches = []
        for manifest in self.repo_path.rglob("*.y*ml"):
            try:
                content = manifest.read_text(encoding="utf-8", errors="ignore").lower()
                if "apiversion" in content and "kind" in content:
                    matches.append(str(manifest.relative_to(self.repo_path)))
            except Exception:
                continue
            if len(matches) >= limit:
                break
        return matches
    
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

        # Detect from deployment files (docker-compose, k8s manifests, Dockerfiles)
        deps_from_deployment = self._parse_deployment_files()

        # Detect from README/docs
        deps_from_readme = self._parse_readme_dependencies()
        
        # Combine and deduplicate
        all_deps = (
            deps_from_configs
            + deps_from_helm
            + deps_from_env
            + deps_from_deployment
            + deps_from_readme
        )
        
        # Deduplicate by name
        seen = set()
        for dep in all_deps:
            name = dep['name']
            if name not in seen:
                external_deps.append(dep)
                seen.add(name)
        
        return external_deps

    def _external_dependency_patterns(self) -> dict[str, tuple[str, str]]:
        """Return known external dependency patterns."""
        return {
            "stripe": ("Stripe", "payment"),
            "aws": ("AWS", "cloud"),
            "s3": ("AWS S3", "storage"),
            "postgres": ("PostgreSQL", "database"),
            "postgresql": ("PostgreSQL", "database"),
            "mysql": ("MySQL", "database"),
            "mariadb": ("MariaDB", "database"),
            "mongodb": ("MongoDB", "database"),
            "redis": ("Redis", "cache"),
            "kafka": ("Kafka", "messaging"),
            "rabbitmq": ("RabbitMQ", "messaging"),
            "elasticsearch": ("Elasticsearch", "search"),
            "opensearch": ("OpenSearch", "search"),
            "auth0": ("Auth0", "authentication"),
            "okta": ("Okta", "authentication"),
            "sendgrid": ("SendGrid", "email"),
            "twilio": ("Twilio", "sms"),
            "slack": ("Slack", "notifications"),
            "datadog": ("Datadog", "monitoring"),
            "sentry": ("Sentry", "error-tracking"),
        }

    def _parse_dependency_files(self) -> list[dict[str, Any]]:
        """Parse package manifests for external dependencies."""
        deps = []
        
        external_patterns = self._external_dependency_patterns()
        
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

    def _parse_readme_dependencies(self) -> list[dict[str, Any]]:
        """Parse README/docs for external service references."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        candidate_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        candidate_files.extend(self.repo_path.rglob("docs/*.md"))
        candidate_files.extend(self.repo_path.rglob("documentation/*.md"))

        for doc in candidate_files:
            try:
                content = doc.read_text(encoding="utf-8", errors="ignore").lower()
                for pattern, (name, dep_type) in external_patterns.items():
                    if pattern in content:
                        deps.append({
                            "name": name,
                            "type": dep_type,
                            "detected_from": str(doc.relative_to(self.repo_path)),
                        })
            except Exception:
                continue

        return deps

    def _parse_deployment_files(self) -> list[dict[str, Any]]:
        """Parse deployment files (docker-compose, k8s manifests, Dockerfiles) for dependencies."""
        deps: list[dict[str, Any]] = []
        external_patterns = self._external_dependency_patterns()

        def add_from_text(text: str, detected_from: str):
            lowered = text.lower()
            for pattern, (name, dep_type) in external_patterns.items():
                if pattern in lowered:
                    deps.append({
                        "name": name,
                        "type": dep_type,
                        "detected_from": detected_from,
                    })

        def add_from_url(url: str, detected_from: str):
            deps.append({
                "name": self._extract_service_name_from_url(url),
                "type": "external_service",
                "url": url,
                "detected_from": detected_from,
            })

        # Dockerfiles
        for dockerfile in self.repo_path.rglob("Dockerfile"):
            try:
                content = dockerfile.read_text(encoding="utf-8", errors="ignore")
                add_from_text(content, str(dockerfile.relative_to(self.repo_path)))
                for url in re.findall(r'https?://[^\s"\']+', content):
                    add_from_url(url, str(dockerfile.relative_to(self.repo_path)))
            except Exception:
                continue

        # docker-compose files
        compose_files = list(self.repo_path.rglob("docker-compose*.y*ml"))
        for compose_file in compose_files:
            try:
                data = yaml.safe_load(compose_file.read_text(encoding="utf-8", errors="ignore"))
                if not isinstance(data, dict):
                    continue
                services = data.get("services", {}) or {}
                for service in services.values():
                    if not isinstance(service, dict):
                        continue
                    image = service.get("image")
                    if isinstance(image, str):
                        add_from_text(image, str(compose_file.relative_to(self.repo_path)))
                    env = service.get("environment")
                    env_values = []
                    if isinstance(env, dict):
                        env_values.extend(str(v) for v in env.values())
                    elif isinstance(env, list):
                        for item in env:
                            if isinstance(item, str) and "=" in item:
                                env_values.append(item.split("=", 1)[1])
                            elif isinstance(item, str):
                                env_values.append(item)
                    for value in env_values:
                        add_from_text(value, str(compose_file.relative_to(self.repo_path)))
                        for url in re.findall(r'https?://[^\s"\']+', value):
                            add_from_url(url, str(compose_file.relative_to(self.repo_path)))
            except Exception:
                continue

        # Kubernetes manifests (light scan)
        for manifest in self.repo_path.rglob("*.y*ml"):
            try:
                content = manifest.read_text(encoding="utf-8", errors="ignore")
                snippet = content[:4000].lower()
                if "apiversion" not in snippet or "kind" not in snippet:
                    continue

                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    images = self._find_manifest_images(doc)
                    for image in images:
                        add_from_text(image, str(manifest.relative_to(self.repo_path)))
                    for url in self._find_external_urls(doc):
                        add_from_url(url, str(manifest.relative_to(self.repo_path)))
            except Exception:
                continue

        return deps

    def _find_manifest_images(self, data: Any) -> list[str]:
        """Recursively collect image references from k8s manifests."""
        images = []
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "image" and isinstance(value, str):
                    images.append(value)
                else:
                    images.extend(self._find_manifest_images(value))
        elif isinstance(data, list):
            for item in data:
                images.extend(self._find_manifest_images(item))
        return images
    
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
        """Generate 1-sentence system purpose using LLM or README extraction."""
        # First try to extract from README without LLM
        readme = self.repo_path / "README.md"
        
        if readme.exists():
            try:
                with open(readme, 'r', encoding='utf-8') as f:
                    content = f.read(3000)  # First 3000 chars
                    
                # Look for common description patterns in README
                # Pattern 1: First paragraph after title
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                description = None
                
                for i, line in enumerate(lines):
                    # Skip title lines
                    if line.startswith('#'):
                        continue
                    # Skip badges, images, links at start
                    if line.startswith('[![') or line.startswith('![') or line.startswith('<'):
                        continue
                    # Found first substantial content line
                    if len(line) > 30 and not line.startswith('|'):
                        description = line
                        break
                
                # Clean up the description
                if description:
                    # Remove markdown formatting
                    description = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', description)  # Remove links
                    description = re.sub(r'[*_`]', '', description)  # Remove formatting
                    description = description.strip()
                    
                    # Ensure it's one sentence
                    sentences = re.split(r'[.!?]', description)
                    if sentences and len(sentences[0]) > 20:
                        first_sentence = sentences[0].strip()
                        if not first_sentence.endswith('.'):
                            first_sentence += '.'
                        return first_sentence
                    
                    # If no sentence boundary, take first 150 chars
                    if len(description) > 150:
                        description = description[:150].rsplit(' ', 1)[0] + '...'
                    return description
                        
            except Exception as e:
                logger.debug(f"Failed to read README: {e}")
        
        # Try with LLM if available
        llm = self.llm_manager
        if llm is not None:
            # Fallback: use directory structure
            dirs = [d.name for d in self.repo_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            context = f"Repository structure: {', '.join(dirs[:10])}"
            
            prompt = f"""Describe the system purpose in ONE sentence.

Repository info:
{context}

Answer format: "This system [does something]."

Your answer:"""
            
            try:
                response = llm.generate_text(
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
                logger.debug(f"Failed to generate system purpose with LLM: {e}")
        
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
        top_contributors = self._get_top_git_contributors(max_contributors=5)
        
        # Try LLM enrichment first if available
        if top_contributors and self.llm_manager:
            suggested_team = self._suggest_team_name_from_contributors(top_contributors)
            if suggested_team and suggested_team != "Unknown":
                return suggested_team
        
        # If git contributors found but no LLM or LLM failed, use top contributor name/email
        if top_contributors:
            first_contributor = top_contributors[0]
            first_email = first_contributor[0]
            
            # Try to extract name from git log with author name
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
                    return author_name
            except Exception:
                pass
            
            # Extract domain from email (e.g., john@team-name.com -> team-name)
            email_match = re.search(r'@([^.]+)', first_email)
            if email_match:
                domain = email_match.group(1)
                # Clean up common patterns
                domain = domain.replace('-', ' ').replace('_', ' ').title()
                return domain
            
            # Last resort: use the email itself
            return first_email
        
        return "Unassigned"
    
    def _get_top_git_contributors(self, max_contributors: int = 3) -> list[tuple[str, int]]:
        """Get top contributors from git history.
        
        Returns:
            List of tuples (email, commit_count) sorted by commit count
        """
        if not (self.repo_path / ".git").exists():
            return []
        
        try:
            # Run git shortlog to get contributor stats (with email addresses)
            result = subprocess.run(
                ['git', 'shortlog', '-sne', '--all'],
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

                # Extract commit count and email (or name if no email)
                match = re.search(r'\s+(\d+)\s+(.+?)(?:\s+<([^>]+)>)?$', line)
                if match:
                    commit_count = int(match.group(1))
                    name = match.group(2).strip()
                    email = match.group(3) if match.group(3) else name
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
        llm = self.llm_manager
        if llm is None or not contributors:
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
            response = llm.generate_text(
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
    
    def _infer_data_classification(self) -> str:
        """Infer data classification based on data handling patterns.
        
        Classifications (from image):
        - PII: Personal Identifiable Information
        - Credit-Card: Payment/financial data
        - Legal/Security: Compliance-related data
        - General: No sensitive data
        """
        data_indicators = {
            'pii': 0,
            'financial': 0,
            'legal': 0,
        }
        
        # Check for common sensitive data patterns in code
        sensitive_keywords = {
            'pii': ['email', 'phone', 'address', 'name', 'user', 'customer', 'profile', 'gdpr', 'ccpa'],
            'financial': ['payment', 'credit', 'card', 'invoice', 'transaction', 'billing', 'stripe', 'paypal'],
            'legal': ['compliance', 'audit', 'legal', 'security', 'encryption', 'auth', 'permission'],
        }
        
        # Scan Python files for sensitive data handling
        for py_file in self.repo_path.rglob("*.py"):
            if any(part in str(py_file) for part in ['.git', 'node_modules', '__pycache__', 'test']):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read(5000).lower()  # First 5000 chars
                    
                for category, keywords in sensitive_keywords.items():
                    for keyword in keywords:
                        if keyword in content:
                            data_indicators[category] += 1
            except Exception:
                continue
        
        # Check environment variables and config files
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
    
    def _extract_level2_containers(self):
        """Extract Level 2: Containers (Deployable Units).
        
        Uses the modular ContainerManager to detect:
        - Services (from projects/ or services/)
        - Databases (from docker-compose or K8s)
        - Frontends (React, Vue, Angular apps)
        - Workers/Jobs
        """
        # Use container manager to detect all containers
        self.containers = self.container_manager.detect_all_containers()

    def _extract_level4_code_details(self):
        """
        Run detailed AST-based extraction on Python containers.
        """
        python_containers = [
            c for c in self.containers.values() 
            if c.get('technology') == 'Python'
        ]

        excluded_dirs = {'node_modules', 'test', 'tests', '__tests__', '__pycache__', '.git', 'venv', '.venv'}
        excluded_files = {'__init__.py', '__main__.py'}

        def iter_python_files(root: Path):
            for file_path in root.rglob('*.py'):
                if any(excluded in file_path.parts for excluded in excluded_dirs):
                    continue
                if file_path.name in excluded_files:
                    continue
                yield file_path

        for container in python_containers:
            container_path_str = container.get('path', '')
            if container_path_str in {'.', ''}:
                container_root = self.repo_path
            else:
                container_root = self.repo_path / container_path_str

            if not container_root.exists():
                continue

            for py_file in iter_python_files(container_root):
                try:
                    if self.ast_extractor.can_handle(py_file):
                        self.ast_extractor.extract(py_file)
                except Exception as e:
                    logger.warning(f"Failed to extract from {py_file}: {e}")

        self.detailed_entities = self.ast_extractor.entities
        self.detailed_relationships = self.ast_extractor.relationships
        
        # Resolve relationship placeholders
        self._resolve_relationships()
        
        # Link components to AST entities
        self._link_components_to_entities()
    
    def _resolve_relationships(self):
        """
        Attempt to resolve named relationship targets to concrete entity IDs.
        Separates internal references from external dependencies.
        """
        # Build map of internal entities
        entity_map = {e.name: e.id for e in self.detailed_entities if e.id}
        entity_map.update({f"{e.file_path}::{e.name}": e.id for e in self.detailed_entities if e.id})
        
        # Known external libraries (expandable)
        external_references = {
            'BaseModel', 'BaseSettings', 'Field', 'validator',  # Pydantic
            'FastAPI', 'APIRouter', 'Depends', 'HTTPException',  # FastAPI
            'Enum', 'dataclass', 'ABC', 'abstractmethod',  # Python stdlib
            'List', 'Dict', 'Optional', 'Any', 'Union',  # typing
            'logging', 'datetime', 'Path', 'json', 'yaml',  # Common modules
        }

        for rel in self.detailed_relationships:
            target_name = None
            if rel.attributes:
                target_name = rel.attributes.get('target_entity_name')

            if rel.target_entity_id in entity_map.values():
                continue

            if not target_name:
                target_name = rel.target_entity_id

            if target_name:
                target_id = entity_map.get(target_name)
                if target_id:
                    rel.target_entity_id = target_id
                elif target_name in external_references or '.' in target_name:
                    rel.attributes['is_external'] = True
    
    def _link_components_to_entities(self):
        """Link C4 Level 3 components (API endpoints) to AST-extracted function entities."""
        for component in self.components.values():
            func_name = component.get('function_name')
            file_path = component.get('file')
            
            if func_name and file_path:
                # Find matching AST entity
                matching_entity = next(
                    (e for e in self.detailed_entities 
                     if e.name == func_name and e.file_path == file_path),
                    None
                )
                if matching_entity:
                    component['ast_entity_id'] = matching_entity.id
                    component['signature'] = matching_entity.signature
                    component['documentation'] = matching_entity.documentation
    
    def _extract_level3_components(self):
        """Extract Level 3: Components using AST for Python and LanguageDetectors for others.
        
        Only registers components if:
        - Python: AST finds function with decorator matching entry_point_patterns
        - Other languages: LanguageDetector finds matching patterns
        
        If container has >10 components, uses LLM to suggest functional groups.
        """
        logger.info("Extracting components using AST for Python and detectors for other languages...")
        
        # Track components per container for grouping
        components_by_container = defaultdict(list)
        
        # 1. Extract Python entry points using AST
        python_extractor = PythonASTExtractor(self.repo_path)
        python_files = list(self.repo_path.rglob("*.py"))
        
        # Filter out excluded directories
        excluded_dirs = {'node_modules', 'test', 'tests', '__tests__', '__pycache__', '.git', 'venv', '.venv'}
        python_files = [
            f for f in python_files 
            if not any(excluded in f.parts for excluded in excluded_dirs)
        ]
        
        logger.info(f"Scanning {len(python_files)} Python files for entry point decorators...")
        
        for py_file in python_files:
            try:
                # Extract all entities from this file
                entities, _ = python_extractor.extract(py_file)
                
                # Find functions with route decorators (entry points)
                for entity in entities:
                    if entity.entity_type != CodeEntityType.FUNCTION:
                        continue
                    
                    decorators = entity.attributes.get('decorators', [])
                    if not decorators:
                        continue
                    
                    # Check if any decorator matches entry point patterns
                    is_entry_point = any(
                        self._is_route_decorator(dec) for dec in decorators
                    )
                    
                    if is_entry_point:
                        # Extract endpoint info
                        endpoint_info = self._extract_route_info_from_decorators(decorators, entity.name)
                        if endpoint_info:
                            container = self._infer_container_from_path(py_file)
                            rel_path = py_file.relative_to(self.repo_path)
                            
                            component = {
                                'c4_level': 3,
                                'type': 'component',
                                'name': f"{endpoint_info['method']} {endpoint_info['path']}",
                                'component_type': 'API Endpoint',
                                'container': container,
                                'file': str(rel_path),
                                'line_start': entity.line_start,
                                'signature': entity.signature,
                                'documentation': entity.documentation,
                                'endpoint_path': endpoint_info['path'],
                                'endpoint_method': endpoint_info['method'],
                            }
                            
                            component_id = f"endpoint_{entity.id}"
                            self.components[component_id] = component
                            components_by_container[container].append(component)
                            
            except Exception as e:
                logger.warning(f"Failed to parse {py_file}: {e}")
        
        logger.info(f"Found {len(self.components)} Python entry point components")

        # 1b. Extract class-level components for deeper Component diagrams
        class_component_count = 0
        for entity in self.detailed_entities:
            if entity.entity_type != CodeEntityType.CLASS:
                continue

            component_type = self._classify_component(entity)
            if not component_type:
                continue

            try:
                file_path = Path(entity.file_path)
                container = self._infer_container_from_path(file_path)
                rel_path = file_path.relative_to(self.repo_path)
            except Exception:
                container = None
                rel_path = entity.file_path

            component_id = f"class_{entity.id}"
            if component_id in self.components:
                continue

            component = {
                'c4_level': 3,
                'type': 'component',
                'name': entity.name,
                'component_type': component_type,
                'container': container,
                'file': str(rel_path),
                'line_start': entity.line_start,
                'signature': entity.signature,
                'documentation': entity.documentation,
                'component_kind': 'Class',
            }

            self.components[component_id] = component
            components_by_container[container].append(component)
            class_component_count += 1

        if class_component_count:
            logger.info(f"Added {class_component_count} class-level components")
        
        # 2. Fall back to LanguageDetectors for non-Python files
        for detector in self.language_detectors:
            if isinstance(detector, PythonLanguageDetector):
                continue  # Already handled above
            
            extensions = detector.get_file_extensions()
            for ext in extensions:
                files = list(self.repo_path.rglob(f"*{ext}"))
                files = [
                    f for f in files 
                    if not any(excluded in f.parts for excluded in excluded_dirs)
                ]
                
                logger.info(f"Scanning {len(files)} {ext} files with {detector.__class__.__name__}...")
                
                for file_path in files:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        entry_points = detector.extract_entry_points(file_path, content)
                        
                        for point in entry_points:
                            container = self._infer_container_from_path(file_path)
                            rel_path = file_path.relative_to(self.repo_path)
                            
                            component = {
                                'c4_level': 3,
                                'type': 'component',
                                'name': point.get('name', 'Unknown'),
                                'component_type': 'API Endpoint',
                                'container': container,
                                'file': str(rel_path),
                                'line_number': point.get('line_number'),
                                'endpoint_path': point.get('path'),
                                'endpoint_method': point.get('method'),
                            }
                            
                            component_id = f"endpoint_{file_path.name}_{point.get('name')}"
                            self.components[component_id] = component
                            components_by_container[container].append(component)
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse {file_path}: {e}")
        
        logger.info(f"Total components extracted: {len(self.components)}")

        # 4. Fallback: add infra components for containers with no code-level components
        self._add_infra_components_for_empty_containers(components_by_container)
        
        # 3. Group components by functional groups if container has >10 components
        self._apply_functional_grouping(components_by_container)

    def _add_infra_components_for_empty_containers(self, components_by_container: dict[str, list]):
        """Create minimal components from Helm/Kustomize manifests when no code components exist."""
        for container_name, container in self.containers.items():
            if components_by_container.get(container_name):
                continue

            container_path = self.repo_path / container.get('path', '')
            infra_components = self._extract_infra_components(container_path)

            for comp in infra_components:
                component_id = f"infra_{container_name}_{comp['name'].lower().replace(' ', '_')}"
                component = {
                    'c4_level': 3,
                    'type': 'component',
                    'name': comp['name'],
                    'component_type': comp['component_type'],
                    'container': container_name,
                    'file': comp.get('file'),
                    'line_start': None,
                    'signature': None,
                    'documentation': None,
                    'component_kind': 'Manifest',
                }
                self.components[component_id] = component
                components_by_container[container_name].append(component)

    def _extract_infra_components(self, container_path: Path) -> list[dict[str, Any]]:
        """Extract infra-level components from Helm/Kustomize manifests."""
        components = []

        # Helm chart templates
        chart_templates = container_path / 'chart' / 'templates'
        if chart_templates.exists():
            for file_path in chart_templates.rglob('*.yaml'):
                name = file_path.stem.replace('-', ' ').replace('_', ' ').title()
                comp_type = self._infer_infra_component_type(file_path.name)
                rel_path = file_path.relative_to(self.repo_path)
                components.append({
                    'name': name,
                    'component_type': comp_type,
                    'file': str(rel_path),
                })

        # Kustomize base
        kustomize_dir = container_path / 'kustomize'
        if kustomize_dir.exists():
            for file_path in kustomize_dir.rglob('*.yaml'):
                if file_path.name == 'kustomization.yaml':
                    continue
                name = file_path.stem.replace('-', ' ').replace('_', ' ').title()
                comp_type = self._infer_infra_component_type(file_path.name)
                rel_path = file_path.relative_to(self.repo_path)
                components.append({
                    'name': name,
                    'component_type': comp_type,
                    'file': str(rel_path),
                })

        return components

    def _infer_infra_component_type(self, filename: str) -> str:
        """Infer infra component type from manifest filename."""
        name = filename.lower()
        if 'deployment' in name:
            return 'Deployment'
        if 'service' in name:
            return 'Service'
        if 'ingress' in name or 'route' in name:
            return 'Ingress'
        if 'configmap' in name:
            return 'ConfigMap'
        if 'secret' in name:
            return 'Secret'
        if 'statefulset' in name:
            return 'StatefulSet'
        if 'job' in name or 'cronjob' in name:
            return 'Job'
        if 'serviceaccount' in name:
            return 'Service Account'
        if 'role' in name or 'rbac' in name:
            return 'RBAC'
        return 'Infrastructure'
    
    def _link_components_to_containers(self):
        """Create relationships between components and their containers."""
        for comp_id, component in self.components.items():
            container_name = component.get('container')
            
            # Find the matching container
            for cont_id, container in self.containers.items():
                if container['name'] == container_name:
                    # Add relationship: component -> container
                    if 'components' not in container:
                        container['components'] = []
                    
                    container['components'].append({
                        'id': comp_id,
                        'name': component['name'],
                        'type': component.get('component_type', 'Component')
                    })
                    
                    # Store the relationship for the graph
                    component['container_id'] = cont_id
                    break
    
    def _apply_functional_grouping(self, components_by_container: dict[str, list]):
        """Use LLM to suggest functional groups for containers with >10 components."""
        for container, components in components_by_container.items():
            if len(components) <= 10:
                continue
            
            logger.info(f"Container '{container}' has {len(components)} components, applying LLM grouping...")
            
            if not self.llm_manager:
                logger.warning("LLM not available, skipping functional grouping")
                continue
            
            # Extract endpoint paths for LLM analysis
            endpoint_paths = [
                comp.get('endpoint_path', comp.get('name', ''))
                for comp in components
            ]
            
            # Ask LLM to suggest 3 functional groups
            prompt = f"""Given these API endpoints from a '{container}' service:

{chr(10).join(f"- {path}" for path in endpoint_paths[:50])}

Suggest exactly 3 functional group names that best categorize these endpoints.
Examples: "Authentication", "User Management", "Data Processing", "Reporting", etc.

Return only 3 group names, one per line, no explanations."""
            
            try:
                response = self.llm_manager.complete(prompt, max_tokens=100)
                group_names = [line.strip() for line in response.strip().split('\n') if line.strip()][:3]
                
                if len(group_names) == 3:
                    logger.info(f"LLM suggested groups for {container}: {group_names}")
                    self._reassign_components_to_groups(container, components, group_names)
                else:
                    logger.warning(f"LLM returned {len(group_names)} groups instead of 3, skipping grouping")
                    
            except Exception as e:
                logger.error(f"Failed to get LLM grouping: {e}")
    
    def _reassign_components_to_groups(self, container: str, components: list, group_names: list[str]):
        """Reassign components to functional groups using LLM."""
        if not self.llm_manager or len(group_names) != 3:
            return
        
        # Ask LLM to assign each endpoint to a group
        endpoint_list = '\n'.join(
            f"{i+1}. {comp.get('endpoint_path', comp.get('name', ''))}"
            for i, comp in enumerate(components)
        )
        
        prompt = f"""Given these functional groups:
1. {group_names[0]}
2. {group_names[1]}
3. {group_names[2]}

Assign each endpoint to the most appropriate group (1, 2, or 3):

{endpoint_list}

Return only the group numbers (1, 2, or 3), one per line, matching the endpoint order."""
        
        try:
            response = self.llm_manager.complete(prompt, max_tokens=200)
            assignments = [line.strip() for line in response.strip().split('\n') if line.strip()]
            
            # Update component metadata with group assignment
            for i, comp in enumerate(components):
                if i < len(assignments):
                    try:
                        group_idx = int(assignments[i]) - 1
                        if 0 <= group_idx < 3:
                            comp['functional_group'] = group_names[group_idx]
                    except ValueError:
                        pass
                        
        except Exception as e:
            logger.error(f"Failed to assign components to groups: {e}")
    
    def _extract_route_info_from_decorators(self, decorators: list[str], func_name: str) -> Optional[dict]:
        """Extract route method and path from function decorators."""
        for decorator in decorators:
            lower_dec = decorator.lower()
            for method in ['get', 'post', 'put', 'delete', 'patch']:
                if f'.{method}' in lower_dec:
                    # Try to extract path from decorator
                    # Format: @app.get("/path") or @router.post('/path')
                    import re
                    path_match = re.search(r'["\']([^"\']+)["\']', decorator)
                    if path_match:
                        path = path_match.group(1)
                    else:
                        # Fallback to function name
                        path = f"/api/{func_name.replace('_', '-')}"
                    
                    return {'method': method.upper(), 'path': path}
        return None
    
    def _classify_component(self, class_entity: CodeEntity) -> Optional[str]:
        """Classify a class as an architectural component type.
        
        Returns component type or None if not architecturally significant.
        """
        name = class_entity.name.lower()
        file_path = class_entity.file_path.lower()
        
        # Configuration classes
        if 'config' in name or 'settings' in name or 'config' in file_path:
            return 'Configuration'
        
        # Model/Data classes
        if 'model' in name or 'schema' in name or 'entity' in name or 'models.py' in file_path:
            return 'Data Model'
        
        # Service/Business Logic
        if 'service' in name or 'manager' in name or 'handler' in name:
            return 'Service'
        
        # API/Controller
        if 'controller' in name or 'api' in name or 'router' in name:
            return 'Controller'
        
        # Gateway/Client
        if 'gateway' in name or 'client' in name or 'adapter' in name:
            return 'Integration'
        
        # Repository/DAO
        if 'repository' in name or 'dao' in name:
            return 'Repository'
        
        # Base classes are important
        base_classes = class_entity.attributes.get('base_classes', [])
        if base_classes and len(base_classes) > 0:
            # If it inherits from BaseModel, BaseSettings, ABC, etc.
            for base in base_classes:
                if any(keyword in str(base).lower() for keyword in ['base', 'abc', 'protocol']):
                    return 'Base Class'
        
        # Has decorators (likely framework-specific important classes)
        decorators = class_entity.attributes.get('decorators', [])
        if decorators:
            return 'Decorated Component'
        
        # Default: not architecturally significant
        return None
    
    def _get_module_path(self, file_path: str) -> str:
        """Convert file path to module path (e.g., 'components/ai_factory/config/core.py' -> 'components.ai_factory.config')."""
        path = Path(file_path)
        parts = path.parts[:-1]  # Remove filename
        return '.'.join(parts) if parts else 'root'
    
    def _is_route_decorator(self, decorator: str) -> bool:
        """Check if decorator is a route decorator."""
        route_keywords = ['app.get', 'app.post', 'app.put', 'app.delete', 'app.patch',
                         'router.get', 'router.post', 'router.put', 'router.delete', 'router.patch',
                         'api.get', 'api.post', 'api.put', 'api.delete', 'api.patch']
        return any(kw in decorator.lower() for kw in route_keywords)
    
    def _extract_route_info_from_entity(self, func_entity: CodeEntity) -> Optional[dict]:
        """Extract route path and method from function entity decorators."""
        decorators = func_entity.attributes.get('decorators', [])
        
        for decorator in decorators:
            lower_dec = decorator.lower()
            for method in ['get', 'post', 'put', 'delete', 'patch']:
                if f'.{method}' in lower_dec:
                    # Decorator format: "app.get" or "router.post"
                    # Path would need to be extracted from original source
                    # For now, use function name as fallback
                    path = f"/api/{func_entity.name.replace('_', '-')}"
                    return {'method': method.upper(), 'path': path}
        return None
    
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
            
            # Strategy 2: Match by name similarity (e.g., slurm_gateway in path → slurm_gateway_api container)
            file_path_str = str(rel_path).lower()
            best_match = None
            best_match_score = 0
            
            for container_name, container_info in self.containers.items():
                # Extract keywords from container name
                container_keywords = container_name.lower().replace('-', '_').split('_')
                
                # Count how many keywords appear in the file path
                match_score = sum(1 for keyword in container_keywords if keyword in file_path_str and len(keyword) > 2)
                
                if match_score > best_match_score:
                    best_match = container_name
                    best_match_score = match_score
            
            if best_match and best_match_score > 0:
                return best_match
            
            # Strategy 3: Walk up directory tree to find closest container
            current = file_path.parent
            max_depth = 5
            depth = 0
            
            while (current != self.repo_path and 
                   current.parent != self.repo_path.parent and 
                   depth < max_depth):
                if is_deployable_service(current):
                    return current.name
                current = current.parent
                depth += 1
            
            # Strategy 4: Ultimate fallback to monorepo root container
            root_container = next(
                (c['name'] for c in self.containers.values() if c.get('path') in {'.', ''}),
                None
            )
            if root_container:
                return root_container
            
            # Final fallback: use first available container
            if self.containers:
                return next(iter(self.containers.keys()))
            
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
        llm = self.llm_manager
        if llm is None:
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
            response = llm.generate_text(
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

    def find_repo_root(start: Path) -> Path:
        for parent in [start] + list(start.parents):
            if (parent / ".git").exists():
                return parent
        return start
    
    # Add app to path (go up 3 levels: c4_extractor -> code_extraction -> services -> app)
    app_path = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(app_path))
    
    from infrastructure.llm.llm_manager import LLMManager
    
    repo_root = find_repo_root(app_path)
    monorepo_path = repo_root / "monorepo"
    target_repo = monorepo_path if monorepo_path.exists() else repo_root
    
    # Initialize LLM (optional)
    try:
        import os
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        model = os.getenv("LMSTUDIO_MODEL_NAME", "qwen/qwen2.5-vl-7b")
        llm = LLMManager(lmstudio_url=base_url, default_model=model)
    except Exception:
        llm = None
        print("⚠️  LLM not available, proceeding without system purpose generation")
    
    # Create extractor
    extractor = C4ArchitectureExtractor(target_repo, llm_manager=llm)
    
    # Extract C4 architecture
    c4_architecture = extractor.extract()
    
    # Save
    api_root = repo_root / "sources" / "Api"
    output_file = api_root / "c4_architecture.json" if api_root.exists() else repo_root / "c4_architecture.json"
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
