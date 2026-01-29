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
from collections import Counter
from pathlib import Path
from typing import Any, Optional

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

    def detect_context_actors(self) -> list[dict[str, Any]]:
        """Detect human/system actors for Context diagram."""
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
        except Exception:
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

        # Find K8s manifests
        for manifest in self.repo_path.rglob("*.y*ml"):
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
