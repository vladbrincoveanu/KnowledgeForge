"""System detection for C4 Context level.

Detects:
- System name from project files
- System purpose from README or LLM
- Languages and frameworks
- Actors (users, systems)
- Git metadata
"""

import json
import logging
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib as tomli
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli
import yaml

from app.utils.fs_utils import limited_rglob
from app.domain.constants.technologies import LANGUAGE_EXTENSIONS, FRAMEWORK_INDICATORS

logger = logging.getLogger(__name__)

STEP_HEADING_PATTERN = re.compile(r'^(?:Step|Chapter|Section|Part)\s+\d+', re.IGNORECASE)

# Headings that are clearly not human actors — error messages, code snippets,
# config keys, future-work notes, or troubleshooting entries.
_NON_ACTOR_HEADING_RE = re.compile(
    r'connection\s+refused|timed?\s+out|error|failed|exception|traceback'
    r'|^\s*note\s*:|^\s*future\s*:|^\s*todo\s*:|^\s*fixme'
    r'|=\s*true|=\s*false|=\s*none|={2,}'   # config values / code
    r'|namespace\s*=|parameter\s+is\s+ignored'
    r'|^\s*#',                                # Python comment lines used as headings
    re.IGNORECASE,
)


class SystemDetector:
    """Detects system-level information for C4 Context."""

    def __init__(self, repo_path: Path, llm_manager=None):
        """Initialize system detector.

        Args:
            repo_path: Path to repository
            llm_manager: Optional LLM for generating descriptions
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager

    def detect_system_name(self) -> str:
        """Detect system name from project files or use LLM."""
        # Try package.json
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    if 'name' in data:
                        return data['name']
            except (OSError, json.JSONDecodeError, ValueError):
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
            except (OSError, json.JSONDecodeError, ValueError):
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
            except (OSError, ValueError):
                pass

        # Try .sln file (Visual Studio solution)
        sln_files = list(self.repo_path.glob("*.sln"))
        if sln_files:
            return sln_files[0].stem

        # Try single .csproj at repo root
        csproj_files = list(self.repo_path.glob("*.csproj"))
        if csproj_files:
            csproj = csproj_files[0]
            try:
                tree = ET.parse(str(csproj))
                assembly_elem = tree.getroot().find(".//AssemblyName")
                if assembly_elem is not None and assembly_elem.text:
                    return assembly_elem.text.strip()
            except ET.ParseError:
                pass
            return csproj.stem

        # Use LLM to generate a better project name if available
        if self.llm_manager and readme_content:
            try:
                repo_url = self.get_repository_root_url()
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

    def generate_system_purpose(self) -> str:
        """Generate 1-sentence system purpose using LLM or README extraction."""
        # First try to extract from README without LLM
        readme = self.repo_path / "README.md"

        if readme.exists():
            try:
                with open(readme, 'r', encoding='utf-8') as f:
                    content = f.read(3000)  # First 3000 chars

                # Look for common description patterns in README
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

    def detect_languages(self) -> list[dict[str, Any]]:
        """Detect primary languages by file extension frequency."""
        ext_counts: Counter[str] = Counter()
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".tox", ".pytest_cache",
        }

        for file_path in limited_rglob(self.repo_path, "*"):
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

    def detect_frameworks(self) -> list[dict[str, Any]]:
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

        for manifest in limited_rglob(self.repo_path, "*"):
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
                elif manifest.name == "pyproject.toml":
                    content = manifest.read_text(encoding="utf-8", errors="ignore")
                    try:
                        pyproject = tomli.loads(content)
                    except Exception:
                        content_lower = content.lower()
                        for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                            if indicator in content_lower:
                                add_framework(lang, fw, rel_path)
                        continue
                    deps: list[str] = []
                    project = pyproject.get("project", {})
                    deps.extend(project.get("dependencies", []))
                    for extras in project.get("optional-dependencies", {}).values():
                        deps.extend(extras)
                    dep_names = set()
                    for dep in deps:
                        name = dep.split("/")[0].split(" ")[0].lower()
                        dep_names.add(name)
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in dep_names:
                            add_framework(lang, fw, rel_path)
                else:
                    content = manifest.read_text(encoding="utf-8", errors="ignore").lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in content:
                            add_framework(lang, fw, rel_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue

        # Scan .csproj files for .NET frameworks
        for csproj in limited_rglob(self.repo_path, "*.csproj"):
            if not csproj.is_file():
                continue
            rel_path = str(csproj.relative_to(self.repo_path))
            try:
                tree = ET.parse(str(csproj))
                root = tree.getroot()

                # Determine .NET version from TargetFramework
                dotnet_version = None
                for tag in ("TargetFramework", "TargetFrameworks"):
                    elem = root.find(f".//{tag}")
                    if elem is not None and elem.text:
                        dotnet_version = elem.text.strip().split(";")[0]
                        break

                # Collect package names and run through indicator matching
                packages: list[str] = []
                for ref in root.findall(".//PackageReference"):
                    include = ref.get("Include", "")
                    if include:
                        packages.append(include)

                if packages:
                    packages_text = " ".join(packages).lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in packages_text:
                            entry: dict[str, Any] = {
                                "language": lang,
                                "framework": fw,
                                "detected_from": rel_path,
                            }
                            if dotnet_version:
                                entry["version"] = dotnet_version
                            key = (lang, fw)
                            if key not in seen:
                                frameworks.append(entry)
                                seen.add(key)
                elif dotnet_version:
                    # No recognisable packages but we know it's .NET
                    key = ("C#", "ASP.NET Core")
                    if key not in seen:
                        frameworks.append({
                            "language": "C#",
                            "framework": "ASP.NET Core",
                            "version": dotnet_version,
                            "detected_from": rel_path,
                        })
                        seen.add(key)
            except ET.ParseError:
                continue

        return frameworks

    def detect_context_actors(self) -> list[dict[str, Any]]:
        """Detect human/system actors for Context diagram."""
        actor_candidates: dict[str, dict[str, str]] = {}
        role_keywords = {
            # Generic roles
            'user': ('User', 'Uses the system'),
            'admin': ('Administrator', 'Administers and configures the system'),
            'operator': ('Operator', 'Operates and monitors the system'),
            'developer': ('Developer', 'Develops and integrates with the system'),
            'engineer': ('Engineer', 'Builds and maintains the system'),
            'client': ('API Client', 'Consumes the system API'),
            'customer': ('Customer', 'End-customer of the service'),
            'analyst': ('Analyst', 'Analyses data from the system'),
            # CMS / content management roles
            'editor': ('Content Editor', 'Creates and edits content'),
            'author': ('Content Author', 'Authors and publishes content'),
            'publisher': ('Content Publisher', 'Publishes and releases content'),
            'marketing': ('Marketing User', 'Creates and manages marketing content'),
            'webmaster': ('Webmaster', 'Manages web content and configuration'),
            'reviewer': ('Content Reviewer', 'Reviews and approves content'),
            'contributor': ('Contributor', 'Contributes content to the system'),
            'moderator': ('Moderator', 'Moderates and curates content'),
            # Commerce / product roles
            'merchant': ('Merchant', 'Manages product catalogue and pricing'),
            'seller': ('Seller', 'Lists and manages products'),
            'buyer': ('Buyer', 'Purchases products through the system'),
            'shopper': ('Shopper', 'Browses and purchases products'),
        }

        def normalize_heading_actor_name(heading: str, fallback: str) -> str:
            cleaned = re.sub(r'^[#\-\*\s]+', '', heading).strip(" :")
            if not cleaned:
                return fallback
            return cleaned if len(cleaned) <= 60 else fallback

        def clean_actor_description(text: str, fallback: str) -> str:
            cleaned = re.sub(r'[`*_#>-]', '', str(text or '')).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned)
            if not cleaned:
                return fallback
            sentence = re.split(r'(?<=[.!?])\s+', cleaned, maxsplit=1)[0].strip()
            return sentence or fallback

        def remember_actor(
            name: str,
            description: str,
            *,
            detected_from: str,
            detection_method: str,
            evidence: str,
        ) -> None:
            actor_candidates[name] = {
                "name": name,
                "type": "person",
                "description": description,
                "detected_from": detected_from,
                "detection_method": detection_method,
                "evidence": evidence,
            }

        candidate_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                candidate_files.append(path)

        candidate_files.extend(limited_rglob(self.repo_path, "docs/*.md"))
        candidate_files.extend(limited_rglob(self.repo_path, "documentation/*.md"))

        # Detect system domain from repo name for smarter fallback
        system_name_lower = self.repo_path.name.lower()
        is_cms = any(k in system_name_lower for k in ('cms', 'content', 'editorial', 'publishing', 'blog', 'wiki'))
        is_commerce = any(k in system_name_lower for k in ('shop', 'store', 'commerce', 'cart', 'checkout', 'catalog'))

        for doc in candidate_files:
            try:
                rel_path = str(doc.relative_to(self.repo_path))
                with open(doc, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                in_code_block = False
                for idx, line in enumerate(lines):
                    # Track fenced code blocks — skip content inside them
                    stripped = line.strip()
                    if stripped.startswith('```') or stripped.startswith('~~~'):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        continue

                    line_lower = line.lower()
                    supporting_line = ""
                    for candidate in lines[idx + 1: idx + 4]:
                        candidate_text = candidate.strip()
                        if candidate_text and not candidate_text.startswith('#'):
                            supporting_line = candidate_text
                            break

                    # Prefer headings for roles/personas
                    if stripped.startswith('#'):
                        raw_heading = stripped
                        heading_text = raw_heading.lstrip('#').strip()
                        # Skip step/chapter headings and non-actor headings
                        if STEP_HEADING_PATTERN.match(heading_text):
                            continue
                        if _NON_ACTOR_HEADING_RE.search(heading_text):
                            continue
                        for key, (label, desc) in role_keywords.items():
                            # Word-boundary match — prevents "user" matching "multiuser"
                            if re.search(r'\b' + re.escape(key) + r'\b', line_lower):
                                remember_actor(
                                    normalize_heading_actor_name(heading_text, label),
                                    clean_actor_description(supporting_line, desc),
                                    detected_from=rel_path,
                                    detection_method="documentation_heading",
                                    evidence=raw_heading,
                                )
                    # Catch inline mentions of CLI or SDK usage (not in code blocks)
                    if re.search(r'\bcli\b', line_lower):
                        remember_actor(
                            'CLI User',
                            'Uses the command-line interface',
                            detected_from=rel_path,
                            detection_method="documentation_mention",
                            evidence=stripped,
                        )
                    if re.search(r'\bsdk\b', line_lower) or 'api client' in line_lower:
                        remember_actor(
                            'API Client',
                            'Consumes the system API',
                            detected_from=rel_path,
                            detection_method="documentation_mention",
                            evidence=stripped,
                        )
                    # CMS-specific inline patterns
                    if any(p in line_lower for p in ('content editor', 'content manager', 'cms user')):
                        remember_actor(
                            'Content Editor',
                            'Creates and manages CMS content',
                            detected_from=rel_path,
                            detection_method="documentation_mention",
                            evidence=line.strip(),
                        )
                    if any(p in line_lower for p in ('marketing user', 'marketing team', 'marketer')):
                        remember_actor(
                            'Marketing User',
                            'Creates and manages marketing content',
                            detected_from=rel_path,
                            detection_method="documentation_mention",
                            evidence=line.strip(),
                        )
            except Exception:
                continue

        # Domain-aware fallback when nothing detected from documentation
        if not actor_candidates:
            if is_cms:
                remember_actor(
                    'Content Editor',
                    'Creates and manages CMS content',
                    detected_from='repo_name',
                    detection_method='domain_fallback',
                    evidence=self.repo_path.name,
                )
                remember_actor(
                    'Administrator',
                    'Administers and configures the system',
                    detected_from='repo_name',
                    detection_method='domain_fallback',
                    evidence=self.repo_path.name,
                )
            elif is_commerce:
                remember_actor(
                    'Shopper',
                    'Browses and purchases products',
                    detected_from='repo_name',
                    detection_method='domain_fallback',
                    evidence=self.repo_path.name,
                )
                remember_actor(
                    'Merchant',
                    'Manages product catalogue and pricing',
                    detected_from='repo_name',
                    detection_method='domain_fallback',
                    evidence=self.repo_path.name,
                )
            else:
                remember_actor(
                    'User',
                    'Uses the system',
                    detected_from='repo_name',
                    detection_method='generic_fallback',
                    evidence=self.repo_path.name,
                )

        return sorted(actor_candidates.values(), key=lambda actor: actor["name"])

    def detect_environments(self) -> list[str]:
        """Detect deployment environments from values files."""
        environments: list[str] = []
        env_patterns = ['dev', 'development', 'staging', 'stage', 'prod', 'production']

        for values_file in limited_rglob(self.repo_path, "values*.y*ml"):
            filename = values_file.name.lower()
            for env in env_patterns:
                if env in filename:
                    if env in ['dev', 'development']:
                        normalized = 'dev'
                    elif env in ['stage', 'staging']:
                        normalized = 'staging'
                    elif env in ['prod', 'production']:
                        normalized = 'prod'
                    else:
                        normalized = env
                    if normalized not in environments:
                        environments.append(normalized)
                    break

        return environments

    def detect_app_version(self) -> Optional[str]:
        """Detect application version from root-level manifests."""
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict) and data.get("version"):
                    return str(data.get("version"))
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, "rb") as f:
                    data = tomli.load(f)
                project = data.get("project", {})
                if isinstance(project, dict) and project.get("version"):
                    return str(project.get("version"))
                poetry = data.get("tool", {}).get("poetry", {})
                if isinstance(poetry, dict) and poetry.get("version"):
                    return str(poetry.get("version"))
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        for chart_yaml in limited_rglob(self.repo_path, "Chart.yaml"):
            try:
                data = yaml.safe_load(chart_yaml.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict) and data.get("appVersion"):
                    return str(data.get("appVersion"))
            except (OSError, yaml.YAMLError):
                continue

        return None

    def detect_tags(self) -> dict[str, str]:
        """Detect tags/labels from Helm chart metadata."""
        tags: dict[str, str] = {}
        for chart_yaml in limited_rglob(self.repo_path, "Chart.yaml"):
            try:
                data = yaml.safe_load(chart_yaml.read_text(encoding="utf-8", errors="ignore")) or {}
            except (OSError, yaml.YAMLError):
                continue

            keywords = data.get("keywords")
            if isinstance(keywords, list):
                for idx, keyword in enumerate(keywords):
                    tags.setdefault(f"keyword_{idx+1}", str(keyword))

            annotations = data.get("annotations")
            if isinstance(annotations, dict):
                for key, value in annotations.items():
                    clean_key = key.split("/")[-1] if "/" in key else key
                    tags.setdefault(f"annotation_{clean_key}", str(value))

            values_file = chart_yaml.parent / "values.yaml"
            if values_file.exists():
                try:
                    values_data = yaml.safe_load(values_file.read_text(encoding="utf-8", errors="ignore")) or {}
                    if isinstance(values_data, dict) and isinstance(values_data.get("commonLabels"), dict):
                        for key, value in values_data["commonLabels"].items():
                            tags.setdefault(f"label_{key}", str(value))
                except (OSError, yaml.YAMLError):
                    continue

        return tags

    def detect_documentation_url(self) -> Optional[str]:
        """Detect documentation URL from README contents."""
        content = self._read_readme_content()
        if not content:
            return None

        md_links = re.findall(r'\[([^\]]*(?:doc|wiki|runbook|guide|manual)[^\]]*)\]\(([^)]+)\)', content, re.I)
        if md_links:
            return md_links[0][1]

        plain_links = re.findall(r'(?:documentation|docs|wiki|runbook|guide):\s*(https?://[^\s<>\"\']+)', content, re.I)
        if plain_links:
            return plain_links[0]

        doc_platforms = [
            r'https://[^/]*confluence[^/]*/[^\s<>\"\']+',
            r'https://[^/]*notion[^/]*/[^\s<>\"\']+',
            r'https://github\.com/[^/]+/[^/]+/wiki[^\s<>\"\']*',
            r'https://[^/]*gitbook[^/]*/[^\s<>\"\']+',
        ]
        for pattern in doc_platforms:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0]

        return None

    def detect_api_spec_url(self) -> Optional[str]:
        """Detect API documentation URL from README links."""
        content = self._read_readme_content()
        if not content:
            return None

        url_matches = re.findall(r'https?://[^\s<>\"\')]+', content)
        for url in url_matches:
            lowered = url.lower()
            if any(token in lowered for token in ("/docs", "swagger", "openapi", "redoc")):
                return url

        for token in ("/docs", "/swagger", "/openapi"):
            if token in content:
                return token

        return None

    def detect_monitoring_url(self) -> Optional[str]:
        """Detect monitoring dashboard URL from README links."""
        content = self._read_readme_content()
        if not content:
            return None

        url_matches = re.findall(r'https?://[^\s<>\"\')]+', content)
        for url in url_matches:
            lowered = url.lower()
            if any(token in lowered for token in ("grafana", "datadog", "cloudwatch", "newrelic", "sentry")):
                return url

        return None

    def detect_regulatory_frameworks(self) -> list[str]:
        """Detect regulatory frameworks mentioned in README."""
        content = self._read_readme_content().lower()
        if not content:
            return []

        frameworks = []
        patterns = {
            "SOC2": ["soc2", "soc 2"],
            "GDPR": ["gdpr"],
            "HIPAA": ["hipaa"],
            "PCI-DSS": ["pci", "pci-dss", "pci dss"],
            "ISO27001": ["iso27001", "iso 27001"],
        }
        for name, tokens in patterns.items():
            if any(token in content for token in tokens):
                frameworks.append(name)

        return frameworks

    def _read_readme_content(self) -> str:
        for name in ["README.md", "README.rst", "README.txt", "README"]:
            path = self.repo_path / name
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
        return ""

    def get_repository_root_url(self) -> str:
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
        except (subprocess.SubprocessError, OSError):
            return ""

    def extract_git_metadata(self) -> dict[str, Any]:
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
            except (subprocess.SubprocessError, OSError):
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

        # Top contributors
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

    def collect_context_sources(self, frameworks: list[dict[str, Any]]) -> dict[str, Any]:
        """Collect key files used for context extraction."""
        sources: dict[str, Any] = {}

        readme_files = []
        for name in ["README.md", "README.rst", "README.txt"]:
            path = self.repo_path / name
            if path.exists():
                readme_files.append(str(path.relative_to(self.repo_path)))

        for doc in list(limited_rglob(self.repo_path, "docs/*.md"))[:5]:
            readme_files.append(str(doc.relative_to(self.repo_path)))
        for doc in list(limited_rglob(self.repo_path, "documentation/*.md"))[:5]:
            readme_files.append(str(doc.relative_to(self.repo_path)))

        if readme_files:
            sources["readme_files"] = readme_files[:8]

        deployment_files = []
        for dockerfile in limited_rglob(self.repo_path, "Dockerfile"):
            deployment_files.append(str(dockerfile.relative_to(self.repo_path)))
        for compose_file in limited_rglob(self.repo_path, "docker-compose*.y*ml"):
            deployment_files.append(str(compose_file.relative_to(self.repo_path)))

        # Find K8s manifests
        for manifest in limited_rglob(self.repo_path, "*.y*ml"):
            if len(deployment_files) >= 10:
                break
            try:
                content = manifest.read_text(encoding="utf-8", errors="ignore").lower()
                if "apiversion" in content and "kind" in content:
                    deployment_files.append(str(manifest.relative_to(self.repo_path)))
            except Exception:
                continue

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
