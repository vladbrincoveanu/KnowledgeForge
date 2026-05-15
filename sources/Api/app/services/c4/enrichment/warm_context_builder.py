import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evidence_corpus import EvidenceCorpus


@dataclass
class SignalFile:
    path: str
    matches: list[str] = field(default_factory=list)


@dataclass
class WarmContext:
    file_tree: list[str]
    evidence: EvidenceCorpus
    signal_files: list[SignalFile]


class WarmContextBuilder:
    def build(self, repo_path: Path, evidence: EvidenceCorpus,
              top_k: int = 20) -> WarmContext:
        tree = self._file_tree(repo_path)
        signals = self._signal_files(repo_path, evidence, top_k)
        return WarmContext(file_tree=tree[:300], evidence=evidence,
                          signal_files=signals)

    def _file_tree(self, repo_path: Path) -> list[str]:
        lines = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in sorted(files):
                if name.startswith("."):
                    continue
                rel = Path(root).relative_to(repo_path)
                lines.append(str(rel / name) if str(rel) != "." else name)
        return lines

    def _signal_files(self, repo_path: Path, evidence: EvidenceCorpus,
                      top_k: int) -> list[SignalFile]:
        signals = []
        for pf in evidence.package_files[:top_k]:
            if not pf.exists():
                continue
            content = pf.read_text(errors="ignore")
            signals.append(SignalFile(path=str(pf), matches=content.splitlines()[:50]))
        for url in evidence.detected_urls[:5]:
            signals.append(SignalFile(path=f"url:{url}", matches=[url]))
        return signals