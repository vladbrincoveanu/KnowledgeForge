"""Source code reader with token budget for LLM component identification."""

from __future__ import annotations

import fnmatch
import io
import os
import re
import tokenize
from dataclasses import dataclass
from typing import Optional

from .tree_sitter_parser import TreeSitterParser

DEFAULT_MAX_TOKENS = 8000
TRUNCATE_THRESHOLD_TOKENS = 500
MAX_LINES_WHEN_TRUNCATING = 20


@dataclass
class SourceFile:
    file_path: str
    content: str
    language: str
    is_truncated: bool = False
    tree_summary: Optional[str] = None


@dataclass
class ContainerSources:
    files: list[SourceFile]
    tree_summary: str
    total_tokens: int


ENTRY_POINT_PATTERNS = [
    "main.py",
    "main.go",
    "main.java",
    "main.ts",
    "main.js",
    "app.py",
    "app.ts",
    "app.js",
    "server.py",
    "server.ts",
    "server.js",
    "index.py",
    "index.ts",
    "index.js",
    "program.*",
    "Program.*",
]

SKIP_DIRS = TreeSitterParser.SKIP_DIRS | {"vendor", "external", "generated"}

SKIP_PATTERNS = [
    *TreeSitterParser.SKIP_PATTERNS,
    "*.test.js",
    "*.spec.js",
    "*.test.tsx",
    "*.spec.tsx",
    "*_pb2.py",
    "*.pb.go",
    "*.g.cs",
]

# Extensions not in TreeSitterParser.LANGUAGE_MAP (e.g. web/systems languages for content reading)
_EXTRA_LANGUAGE_MAP: dict[str, str] = {
    ".jsx": "javascript",
    ".php": "php",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}

LOCK_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "requirements.txt",
    "go.sum",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
}


class SourceReader:
    def __init__(self, parser: Optional[TreeSitterParser] = None) -> None:
        self._parser = parser if parser is not None else TreeSitterParser()

    def read_container_sources(
        self,
        container_path: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ContainerSources:
        files = self._discover_files(container_path)
        prioritized = self._prioritize_files(files)
        tree_summary = self._build_tree_summary(container_path)
        selected, total_tokens = self._apply_token_budget(prioritized, max_tokens)
        return ContainerSources(files=selected, tree_summary=tree_summary, total_tokens=total_tokens)

    def parse_file(self, filepath: str) -> Optional[SourceFile]:
        parsed = self._parser.parse_file(filepath)
        if parsed is None:
            return None
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return None
        return SourceFile(
            file_path=filepath,
            content=content,
            language=parsed.language,
            is_truncated=False,
        )

    def _discover_files(self, container_path: str) -> list[str]:
        discovered: list[str] = []
        for dirpath, dirs, files in os.walk(container_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                if self._should_skip(filename):
                    continue
                full_path = os.path.join(dirpath, filename)
                discovered.append(full_path)
        return discovered

    def _should_skip(self, filename: str) -> bool:
        if filename in LOCK_FILES:
            return True
        for pattern in SKIP_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def _prioritize_files(self, files: list[str]) -> list[str]:
        def sort_key(path: str) -> tuple:
            basename = os.path.basename(path)
            depth = path.count(os.sep)
            is_entry = any(fnmatch.fnmatch(basename, p) for p in ENTRY_POINT_PATTERNS)
            return (0 if is_entry else 1, depth, basename)
        return sorted(files, key=sort_key)

    def _build_tree_summary(self, container_path: str) -> str:
        lines: list[str] = []
        prefix = container_path + os.sep
        for dirpath, dirs, files in os.walk(container_path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            rel = dirpath[len(prefix):] if dirpath.startswith(prefix) else dirpath
            indent = rel.count(os.sep) if rel else 0
            indent_str = "  " * indent
            if rel:
                lines.append(f"{indent_str}{os.path.basename(rel)}/")
            for f in sorted(files):
                if self._should_skip(f):
                    continue
                ext = os.path.splitext(f)[1]
                lines.append(f"{indent_str}  {f}")
        return "\n".join(lines)

    def _apply_token_budget(
        self,
        files: list[str],
        max_tokens: int,
    ) -> tuple[list[SourceFile], int]:
        selected: list[SourceFile] = []
        total_tokens = 0
        for filepath in files:
            content = self._read_file_content(filepath)
            if content is None:
                continue
            tokens = self._estimate_tokens(content)
            if total_tokens + tokens > max_tokens and selected:
                break
            selected.append(SourceFile(
                file_path=filepath,
                content=content,
                language=self._language_from_ext(filepath),
                is_truncated=tokens > TRUNCATE_THRESHOLD_TOKENS,
            ))
            total_tokens += tokens
        return selected, total_tokens

    def _read_file_content(self, filepath: str) -> Optional[str]:
        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext in {".py"}:
                return self._read_python_file(filepath)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return None

    def _read_python_file(self, filepath: str) -> Optional[str]:
        try:
            with open(filepath, "rb") as f:
                raw_bytes = f.read()
            tokens = list(tokenize.tokenize(io.BytesIO(raw_bytes).readline))
            imports = []
            source_lines = raw_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
            import_token = tokenize.IMPORT
            import_from_token = tokenize.IMPORTFROM
            for tok in tokens:
                if tok.type == import_from_token or tok.type == import_token:
                    if tok.string:
                        imports.append(tok.string)
            small_file = len(source_lines) <= TRUNCATE_THRESHOLD_TOKENS
            if small_file:
                return "".join(source_lines)
            import_section = "\n".join(f"import {imp}" for imp in imports[:30]) if imports else ""
            sig_lines: list[str] = []
            func_pattern = re.compile(r"^(\s*)def\s+(\w+)\s*\(")
            class_pattern = re.compile(r"^(\s*)class\s+(\w+)")
            for i, line in enumerate(source_lines[:100], 1):
                func_match = func_pattern.match(line)
                class_match = class_pattern.match(line)
                if func_match:
                    end = i + 10
                    while end <= len(source_lines) and source_lines[end - 1].startswith((" ", "\t")):
                        end += 1
                    body_preview = "".join(source_lines[i-1:min(end, i + MAX_LINES_WHEN_TRUNCATING)])
                    sig_lines.append(body_preview.strip())
                elif class_match:
                    end = i + 20
                    while end <= len(source_lines) and source_lines[end - 1].startswith((" ", "\t")):
                        end += 1
                    body_preview = "".join(source_lines[i-1:min(end, i + MAX_LINES_WHEN_TRUNCATING)])
                    sig_lines.append(body_preview.strip())
            parts: list[str] = []
            if import_section:
                parts.append(f"# Imports:\n{import_section}")
            if sig_lines:
                parts.append(f"# Signatures:\n" + "\n".join(sig_lines[:30]))
            parts.append(f"# File: {os.path.basename(filepath)} ({len(source_lines)} lines, truncated)")
            return "\n\n".join(parts)
        except Exception:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if len(lines) <= TRUNCATE_THRESHOLD_TOKENS:
                return "".join(lines)
            return "".join(lines[:TRUNCATE_THRESHOLD_TOKENS]) + f"\n# ... truncated ({len(lines)} total lines)"

    @staticmethod
    def _language_from_ext(filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        return (
            TreeSitterParser.LANGUAGE_MAP.get(ext)
            or _EXTRA_LANGUAGE_MAP.get(ext, "unknown")
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4
