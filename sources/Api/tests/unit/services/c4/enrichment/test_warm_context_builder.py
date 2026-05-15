from pathlib import Path
from unittest.mock import MagicMock
import pytest
from app.services.c4.enrichment.warm_context_builder import WarmContextBuilder
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus


def _ec(tmp_path):
    return EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                          languages=["python"], frameworks=["fastapi"],
                          deterministic_deps=[], entrypoints=[],
                          detected_urls=[], env_vars=[], docker_images=[],
                          package_files=[Path("requirements.txt")])


def test_build_returns_file_tree(tmp_path):
    (tmp_path / "main.py").write_text("x=1")
    (tmp_path / "a.py").write_text("y=2")
    wc = WarmContextBuilder().build(tmp_path, _ec(tmp_path), top_k=5)
    assert len(wc.file_tree) >= 2
    assert any("main.py" in f for f in wc.file_tree)


def test_build_returns_signal_files(tmp_path):
    (tmp_path / "app.py").write_text("import stripe")
    (tmp_path / "requirements.txt").write_text("stripe==5.0")
    wc = WarmContextBuilder().build(tmp_path, _ec(tmp_path), top_k=5)
    assert len(wc.signal_files) >= 1


def test_top_k_caps_file_tree(tmp_path):
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text(f"x={i}")
    wc = WarmContextBuilder().build(tmp_path, _ec(tmp_path), top_k=5)
    assert len(wc.file_tree) <= 300  # 300 = hard cap, not top_k
