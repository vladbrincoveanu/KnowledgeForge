"""Generate short service descriptions using optional LLM support."""

import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


DESCRIPTION_PROMPT = """You are an engineering assistant.
Summarize the purpose of this service in 1-2 concise sentences (business-level).
Avoid implementation details; focus on the business capability.

Service: {service_name}
Path: {service_path}
Language: {language}

Key files (truncated):
{file_snippets}

Respond with only the description sentence(s).
"""


class ServiceDescriptionGenerator:
    """Generate descriptions from code/docs with optional LLM assistance."""

    def __init__(self, llm_manager: Optional[Any], max_tokens: int = 150, budget: Optional[Any] = None):
        self.llm = llm_manager
        self.max_tokens = max_tokens
        self.budget = budget

    def generate_description(
        self,
        service_name: str,
        service_path: Path,
        language: Optional[str] = None,
        repo_root: Optional[Path] = None,
    ) -> Optional[str]:
        """Return a short description or None if not enough signal."""
        key_files = self._collect_key_files(service_path, repo_root)
        snippets = self._read_snippets(key_files)

        if not snippets:
            return None

        file_snippets = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in snippets.items()
        )

        prompt = DESCRIPTION_PROMPT.format(
            service_name=service_name,
            service_path=str(service_path),
            language=language or "unknown",
            file_snippets=file_snippets,
        )

        # Prefer LLM if available
        if self.llm:
            estimated_tokens = self._estimate_tokens(prompt, self.max_tokens)
            if not self.budget or self.budget.consume(estimated_tokens):
                try:
                    response = self.llm.generate_text(
                        prompt,
                        max_tokens=self.max_tokens,
                        temperature=0.3,
                    )
                    if response:
                        return response.strip().replace("\n", " ")
                except Exception as e:
                    logger.debug(f"LLM description generation failed: {e}")

        # Fallback: extract description from README content
        return self._extract_description_from_readme(service_name, snippets)

    def _extract_description_from_readme(self, service_name: str, snippets: dict[str, str]) -> Optional[str]:
        """Extract a meaningful description from README content without LLM."""
        import re
        
        # Prioritize README files
        readme_content = None
        for path, content in snippets.items():
            if "readme" in path.lower():
                readme_content = content
                break
        
        if not readme_content:
            # Use any available content
            readme_content = next(iter(snippets.values()), "")
        
        if not readme_content:
            return None
        
        # Pre-process: remove HTML tags and content
        # Remove HTML blocks (like <p>, <div>, <a>, etc.)
        readme_content = re.sub(r"<[^>]+>", " ", readme_content)
        # Remove markdown images and badges
        readme_content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", readme_content)
        # Remove markdown links but keep text
        readme_content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", readme_content)
        # Remove HTML entities
        readme_content = re.sub(r"&[a-zA-Z]+;", " ", readme_content)
        # Clean up excessive whitespace
        readme_content = re.sub(r"\s+", " ", readme_content)
        
        # Try to extract description from common README patterns
        lines = readme_content.strip().split("\n")
        description_lines = []
        
        # Skip title/badges and find first meaningful paragraph
        in_description = False
        for line in lines:
            stripped = line.strip()
            
            # Skip empty/short lines
            if not stripped or len(stripped) < 10:
                if in_description and description_lines:
                    break  # End of description paragraph
                continue
            
            # Skip titles
            if stripped.startswith("#"):
                in_description = True  # Start after title
                continue
            
            # Skip badge-like lines (short lines with mostly special chars)
            if len(stripped) < 30 and re.search(r"[|<>\[\]]", stripped):
                continue
            
            # Skip code blocks
            if stripped.startswith("```"):
                break
            
            # Skip tables
            if stripped.startswith("|"):
                continue
            
            # Skip list items initially
            if re.match(r"^[-*]\s", stripped):
                if description_lines:
                    break  # Stop at lists if we already have description
                continue
            
            # Skip lines that look like URLs or paths
            if re.match(r"^https?://", stripped) or "/" in stripped[:20]:
                continue
            
            # This looks like description text - must have some letters
            if re.search(r"[a-zA-Z]{3,}", stripped):
                if in_description or len(description_lines) == 0:
                    in_description = True
                    description_lines.append(stripped)
                    if len(" ".join(description_lines)) > 200:
                        break
        
        if description_lines:
            description = " ".join(description_lines)
            # Clean up and truncate
            description = re.sub(r"\s+", " ", description).strip()
            # Remove any remaining markdown artifacts
            description = re.sub(r"\*+", "", description)
            description = re.sub(r"_+", "", description)
            if len(description) > 250:
                description = description[:247] + "..."
            if description and not description.endswith("."):
                description += "."
            if len(description) > 20:  # Only return if meaningful
                return description
        
        # Fallback: try to find any sentence-like content
        sentences = re.findall(r"[A-Z][^.!?]*[.!?]", readme_content)
        for sentence in sentences:
            if len(sentence) > 30 and len(sentence) < 300:
                return sentence.strip()
        
        return None

    def _collect_key_files(self, service_path: Path, repo_root: Optional[Path] = None) -> list[Path]:
        """Prioritize README/docs and entrypoints."""
        candidates = [
            "README.md",
            "README.rst",
            "readme.md",
            "readme.rst",
            "__init__.py",
            "main.py",
            "app.py",
            "index.py",
            "index.js",
            "index.ts",
        ]

        files: list[Path] = []
        for name in candidates:
            candidate = service_path / name
            if candidate.exists():
                files.append(candidate)

        if repo_root and repo_root != service_path:
            for name in candidates:
                candidate = repo_root / name
                if candidate.exists() and candidate not in files:
                    files.append(candidate)

        return files[:4]  # limit to keep prompts small

    def _read_snippets(self, files: list[Path]) -> dict[str, str]:
        """Read up to ~400 characters per file to keep prompt compact."""
        snippets: dict[str, str] = {}
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                snippets[str(file_path.name)] = text[:800]
            except Exception:
                continue
        return snippets

    def _estimate_tokens(self, prompt: str, max_tokens: int) -> int:
        """Rough heuristic: characters/4 + max tokens."""
        return int(len(prompt) / 4) + max_tokens
