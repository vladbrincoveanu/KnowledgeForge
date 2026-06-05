"""Multi-language Tree-sitter parser for C4 component extraction with incremental parsing."""

from __future__ import annotations

import difflib
import fnmatch
import os
from dataclasses import dataclass
from typing import Any, Optional

from tree_sitter import Tree
from tree_sitter_language_pack import get_parser


@dataclass
class ParsedFile:
    file_path: str
    language: str
    tree: Tree


@dataclass
class _TreeCacheEntry:
    parsed_file: ParsedFile
    old_bytes: bytes
    mtime: float


def _compute_changed_ranges(
    old_text: str, new_text: str, old_bytes: bytes, new_bytes: bytes
) -> list[dict[str, Any]]:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    ranges = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        start_byte = sum(len(l) for l in old_lines[:i1])
        old_end_byte = sum(len(l) for l in old_lines[:i2])
        new_end_byte = sum(len(l) for l in new_lines[:j2])
        start_row, start_col = _byte_offset_to_point(old_bytes, start_byte)
        old_end_row, old_end_col = _byte_offset_to_point(old_bytes, old_end_byte)
        new_end_row, new_end_col = _byte_offset_to_point(new_bytes, new_end_byte)
        ranges.append(
            dict(
                start_byte=start_byte,
                old_end_byte=old_end_byte,
                new_end_byte=new_end_byte,
                start_point=(start_row, start_col),
                old_end_point=(old_end_row, old_end_col),
                new_end_point=(new_end_row, new_end_col),
            )
        )
    return ranges


def _byte_offset_to_point(text: bytes, offset: int) -> tuple[int, int]:
    decoded = text.decode("utf-8", errors="replace")
    row = 0
    line_start = 0
    for line in decoded.splitlines(keepends=True):
        line_end = line_start + len(line.encode("utf-8"))
        if line_end >= offset:
            col = offset - line_start
            return (row, col)
        line_start = line_end
        row += 1
    last_row = decoded.count("\n")
    return (last_row, offset - line_start if line_start < len(text) else 0)


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
        "*_spec.rb",
    ]

    def __init__(self) -> None:
        self._parser_cache: dict[str, Any] = {}
        self._tree_cache: dict[str, _TreeCacheEntry] = {}

    def _get_parser(self, language: str) -> Any:
        if language not in self._parser_cache:
            self._parser_cache[language] = get_parser(language)
        return self._parser_cache[language]

    def parse_file(self, file_path: str) -> Optional[ParsedFile]:
        ext = os.path.splitext(file_path)[1].lower()
        language = self.LANGUAGE_MAP.get(ext)
        if language is None:
            return None

        try:
            new_mtime = os.path.getmtime(file_path)
            with open(file_path, "rb") as f:
                new_bytes = f.read()
        except Exception:
            return None

        cached = self._tree_cache.get(file_path)
        if cached is not None and cached.mtime == new_mtime:
            return cached.parsed_file

        parser = self._get_parser(language)

        if cached is not None:
            old_text = cached.old_bytes.decode("utf-8", errors="replace")
            new_text = new_bytes.decode("utf-8", errors="replace")
            ranges = _compute_changed_ranges(
                old_text, new_text, cached.old_bytes, new_bytes
            )
            if not ranges:
                return cached.parsed_file
            old_tree = cached.parsed_file.tree
            for r in ranges:
                old_tree.edit(**r)
            new_tree = parser.parse(new_bytes, old_tree)
            parsed = ParsedFile(file_path=file_path, language=language, tree=new_tree)
            self._tree_cache[file_path] = _TreeCacheEntry(parsed, new_bytes, new_mtime)
            return parsed

        tree = parser.parse(new_bytes)
        parsed = ParsedFile(file_path=file_path, language=language, tree=tree)
        self._tree_cache[file_path] = _TreeCacheEntry(parsed, new_bytes, new_mtime)
        return parsed

    def parse_directory(
        self, root_path: str, skip_tests: bool = True
    ) -> list[ParsedFile]:
        results: list[ParsedFile] = []

        for dirpath, dirs, files in os.walk(root_path):
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
