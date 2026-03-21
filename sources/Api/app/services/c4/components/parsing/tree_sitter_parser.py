"""Multi-language Tree-sitter parser for C4 component extraction."""

import fnmatch
import os
from dataclasses import dataclass
from typing import Optional

from tree_sitter import Tree
from tree_sitter_language_pack import get_parser


@dataclass
class ParsedFile:
    file_path: str
    language: str
    tree: Tree


class TreeSitterParser:
    LANGUAGE_MAP: dict[str, str] = {
        ".py": "python",
        ".java": "java",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".go": "go",
        ".cs": "csharp",
        ".rs": "rust",
        ".kt": "kotlin",
        ".rb": "ruby",
    }

    SKIP_DIRS: set[str] = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "build",
        "dist",
        ".tox",
        ".mypy_cache",
        "target",
        ".gradle",
    }

    SKIP_PATTERNS: list[str] = [
        "*_test.py",
        "test_*.py",
        "*Test.java",
        "*_test.go",
        "*.test.ts",
        "*.spec.ts",
    ]

    def parse_file(self, file_path: str) -> Optional[ParsedFile]:
        """Parse a single file into a ParsedFile, or return None if unsupported."""
        ext = os.path.splitext(file_path)[1].lower()
        language = self.LANGUAGE_MAP.get(ext)
        if language is None:
            return None

        try:
            parser = get_parser(language)
            with open(file_path, "rb") as f:
                source_bytes = f.read()
            tree = parser.parse(source_bytes)
            return ParsedFile(file_path=file_path, language=language, tree=tree)
        except Exception:
            return None

    def parse_directory(
        self, root_path: str, skip_tests: bool = True
    ) -> list[ParsedFile]:
        """Recursively parse all supported source files under root_path."""
        results: list[ParsedFile] = []

        for dirpath, dirs, files in os.walk(root_path):
            # Prune skip dirs in-place
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            if skip_tests:
                dirs[:] = [d for d in dirs if d != "__tests__"]

            for filename in files:
                if skip_tests and any(
                    fnmatch.fnmatch(filename, pat) for pat in self.SKIP_PATTERNS
                ):
                    continue

                full_path = os.path.join(dirpath, filename)
                parsed = self.parse_file(full_path)
                if parsed is not None:
                    results.append(parsed)

        return results
