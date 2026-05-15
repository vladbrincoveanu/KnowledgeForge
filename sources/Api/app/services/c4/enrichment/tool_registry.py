import os
import re
from pathlib import Path
from typing import Any, Callable

from .graph_writer import EnrichmentGraphWriter
from .json_persister import EnrichmentJSONPersister


class ExtractionToolRegistry:
    def __init__(self, repo_path: Path, graph_writer: Any,
                 persister: Any, ws_emit: Callable[[str, dict], None]):
        self.repo_path = Path(repo_path)
        self.graph_writer = graph_writer
        self.persister = persister
        self.ws_emit = ws_emit
        self._emitted_nodes: list[dict] = []

    def grep(self, pattern: str, path: str = ".") -> list[dict[str, Any]]:
        results = []
        search_root = self.repo_path / path
        for root, _, files in os.walk(search_root):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    text = fpath.read_text(errors="ignore")
                    for m in re.finditer(pattern, text, re.MULTILINE):
                        line_num = text[:m.start()].count("\n") + 1
                        snippet = text[max(0, m.start()-40):m.end()+40]
                        results.append({
                            "file": str(fpath.relative_to(self.repo_path)),
                            "line": line_num,
                            "snippet": snippet,
                        })
                except Exception:
                    pass
        return results

    def read_file(self, path: str) -> dict[str, Any]:
        fpath = self.repo_path / path
        if not fpath.exists():
            return {"content": "", "error": "file not found"}
        try:
            text = fpath.read_text(errors="ignore")
            return {"content": text, "lines": text.count("\n")+1}
        except Exception as e:
            return {"content": "", "error": str(e)}

    def list_dir(self, path: str = ".") -> list[str]:
        d = self.repo_path / path
        if not d.exists():
            return []
        return [str(f.relative_to(d)) for f in d.iterdir()]

    def emit_node(self, type_: str, name: str,
                  props: dict[str, Any]) -> dict[str, Any]:
        node = {"type": type_, "name": name, "props": props}
        self.graph_writer.upsert_node(type_=type_, name=name, props=props)
        self.persister.append({"event": "node_added", **node})
        self.ws_emit("node_added", node)
        self._emitted_nodes.append(node)
        return node

    def emit_edge(self, from_name: str, to_name: str,
                  relationship: str, props: dict[str, Any]) -> None:
        self.graph_writer.upsert_edge(
            from_name=from_name, to_name=to_name,
            relationship=relationship, props=props,
        )
        edge_event = {"event": "edge_added", "from": from_name,
                      "to": to_name, "relationship": relationship}
        self.persister.append(edge_event)
        self.ws_emit("edge_added", {"from": from_name, "to": to_name,
                                    "relationship": relationship})

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "grep",
                "description": "Search files in repo. Args: pattern (regex str), path (str, default '.'). Returns list of {file, line, snippet}.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "read_file",
                "description": "Read file content. Args: path (str relative to repo root). Returns {content, lines} or {error}.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "list_dir",
                "description": "List files in directory. Args: path (str, default '.'). Returns list of filenames.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                },
            },
            {
                "name": "emit_node",
                "description": "Emit a C4 node (external_dep, service, database, etc). Args: type_ (str), name (str), props (dict with confidence, evidence, etc).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type_": {"type": "string"},
                        "name": {"type": "string"},
                        "props": {"type": "object"},
                    },
                    "required": ["type_", "name"],
                },
            },
            {
                "name": "emit_edge",
                "description": "Emit a C4 relationship between two nodes. Args: from_name, to_name, relationship, props.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "from_name": {"type": "string"},
                        "to_name": {"type": "string"},
                        "relationship": {"type": "string"},
                        "props": {"type": "object"},
                    },
                    "required": ["from_name", "to_name", "relationship"],
                },
            },
        ]