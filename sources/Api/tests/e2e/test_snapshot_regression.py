"""Snapshot regression tests for OmniPay extraction.

Run with --snapshot-update to regenerate the snapshot:
    docker compose exec api python -m pytest tests/e2e/test_snapshot_regression.py -v --snapshot-update
"""

import json
from pathlib import Path

import pytest


SNAPSHOT_FILE = Path(__file__).parent / "snapshots" / "omnipay_extraction.json"
DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    import subprocess
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


def _serialize(containers, context):
    """Serialize extraction output deterministically."""
    containers_sorted = sorted(containers, key=lambda c: c.get("name", ""))
    for container in containers_sorted:
        for key in ["relationships", "dependencies_internal"]:
            if key in container and isinstance(container[key], list):
                container[key] = sorted(container[key], key=lambda x: str(x) if x else "")
        if "path" in container:
            container["path"] = str(container["path"])
    return {
        "containers": containers_sorted,
        "system_context": context,
    }


@pytest.fixture
def snapshot_path():
    return SNAPSHOT_FILE


@pytest.fixture
def extraction_output():
    """Run extraction and return deterministic output."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")
    _init_git(DEMO_DIR)

    from app.services.c4.containers.structure_detector import StructureDetector
    from app.services.c4.context.context_manager import ContextManager

    detector = StructureDetector(DEMO_DIR, llm_manager=None)
    containers = detector.detect()

    manager = ContextManager(DEMO_DIR, llm_manager=None)
    context = manager.extract_context()

    return _serialize(containers, context)


@pytest.fixture
def expected_snapshot(snapshot_path):
    """Load expected snapshot, or skip if doesn't exist."""
    if not snapshot_path.exists():
        pytest.skip(
            f"Snapshot file not found: {snapshot_path}. "
            "Run with --snapshot-update to create."
        )
    with open(snapshot_path, "r") as f:
        return json.load(f)


def test_snapshot_exists(snapshot_path):
    """Snapshot file should exist after initial generation."""
    assert snapshot_path.exists(), (
        f"Snapshot file missing: {snapshot_path}. "
        "Run with --snapshot-update to generate."
    )


def test_container_count_matches_snapshot(extraction_output, expected_snapshot):
    """Container count should match snapshot."""
    expected_count = len(expected_snapshot["containers"])
    actual_count = len(extraction_output["containers"])
    assert actual_count == expected_count, (
        f"Container count mismatch: got {actual_count}, expected {expected_count}. "
        "Run with --snapshot-update to update."
    )


def test_all_snapshot_services_present(extraction_output, expected_snapshot):
    """All services in snapshot should be present in extraction."""
    expected_names = {c["name"] for c in expected_snapshot["containers"]}
    actual_names = {c["name"] for c in extraction_output["containers"]}
    missing = expected_names - actual_names
    extra = actual_names - expected_names
    if missing or extra:
        msg = ""
        if missing:
            msg += f"\n  Missing services: {sorted(missing)}"
        if extra:
            msg += f"\n  New services: {sorted(extra)}"
        msg += "\nRun with --snapshot-update to update snapshot."
        pytest.fail(msg)


def test_system_context_has_required_fields(extraction_output):
    """System context should have all required fields."""
    context = extraction_output["system_context"]
    required_fields = [
        "c4_level", "type", "name", "purpose", "domain",
        "owner", "status", "tier", "data_class",
    ]
    missing = [f for f in required_fields if f not in context]
    assert not missing, f"System context missing fields: {missing}"