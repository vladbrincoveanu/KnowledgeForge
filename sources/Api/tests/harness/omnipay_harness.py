"""Shared pytest fixtures for OmniPay demo extraction tests."""

import subprocess
from pathlib import Path
from typing import List, Dict, Any

import pytest


# Path to the OmniPay demo directory inside the Docker container
DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    """Initialize a git repo with a single commit so git-based detectors work."""
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


@pytest.fixture(scope="module")
def demo_dir() -> Path:
    """Return path to the OmniPay demo directory."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")
    return DEMO_DIR


@pytest.fixture(scope="module")
def omnipay_repo(demo_dir: Path) -> Dict[str, Path]:
    """Return a dict mapping service name to its path, with git initialized."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    result = {}
    for subdir in demo_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            result[subdir.name] = subdir
    return result


def extract_containers(repo_path: Path) -> List[Dict[str, Any]]:
    """Run StructureDetector on a repo path and return container list."""
    from app.services.c4.containers.structure_detector import StructureDetector

    detector = StructureDetector(repo_path, llm_manager=None)
    return detector.detect()


def extract_context(repo_path: Path) -> Dict[str, Any]:
    """Run ContextManager on a repo path and return system context."""
    from app.services.c4.context.context_manager import ContextManager

    manager = ContextManager(repo_path, llm_manager=None)
    return manager.extract_context()


@pytest.fixture(scope="module")
def extracted_containers(demo_dir: Path) -> List[Dict[str, Any]]:
    """Extract containers from the full OmniPay demo directory."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    return extract_containers(demo_dir)


@pytest.fixture(scope="module")
def extracted_context(demo_dir: Path) -> Dict[str, Any]:
    """Extract system context from the full OmniPay demo directory."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    return extract_context(demo_dir)
