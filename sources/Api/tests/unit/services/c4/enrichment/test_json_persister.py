import json
from pathlib import Path
import pytest
from app.services.c4.enrichment.json_persister import EnrichmentJSONPersister


@pytest.fixture
def persister(tmp_path):
    return EnrichmentJSONPersister(base_dir=tmp_path, task_id="t1", run_id="r1")


def test_append_writes_jsonl_line(persister, tmp_path):
    persister.append({"event": "node_added", "name": "Stripe"})
    persister.append({"event": "edge_added", "from": "Sys", "to": "Stripe"})
    lines = (tmp_path / "t1.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Stripe"


def test_finalize_writes_snapshot(persister, tmp_path):
    persister.append({"event": "node_added", "name": "A"})
    persister.finalize({"nodes_added": 1, "partial": False})
    snap = json.loads((tmp_path / "t1.json").read_text())
    assert snap["summary"]["nodes_added"] == 1
    assert len(snap["events"]) == 1


def test_rollback_deletes_both_files(persister, tmp_path):
    persister.append({"event": "x"})
    persister.finalize({"x": 1})
    persister.rollback()
    assert not (tmp_path / "t1.jsonl").exists()
    assert not (tmp_path / "t1.json").exists()


def test_rollback_when_files_missing_is_noop(persister):
    persister.rollback()  # must not raise
