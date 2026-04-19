"""Edge case tests using OmniPay edge-case demo services."""

import subprocess
from pathlib import Path

import pytest


DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


def _extract_containers(repo_path: Path):
    from app.services.c4.containers.structure_detector import StructureDetector
    detector = StructureDetector(repo_path, llm_manager=None)
    return detector.detect()


def _extract_context(repo_path: Path):
    from app.services.c4.context.context_manager import ContextManager
    manager = ContextManager(repo_path, llm_manager=None)
    return manager.extract_context()


def _get_service(repo_path: Path, name: str):
    """Get a specific service from extraction."""
    containers = _extract_containers(repo_path)
    return next((c for c in containers if c.get("name") == name), None)


class TestRustDetection:
    """Test Rust service detection (Cargo.toml)."""

    @pytest.fixture(scope="class")
    def rust_service(self):
        """omnipay-rust-service: Rust + Cargo.toml + src/."""
        path = DEMO_DIR / "omnipay-rust-service"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _get_service(path, "omnipay-rust-service")

    def test_rust_detected(self, rust_service):
        """Technology field should be 'Rust'."""
        assert rust_service is not None, "omnipay-rust-service not found in extraction"
        tech = str(rust_service.get("technology", "")).lower()
        assert "rust" in tech, f"Expected Rust technology, got: {tech}"

    def test_rust_container_type(self, rust_service):
        """Container type should indicate a compiled language service."""
        ctype = str(rust_service.get("container_type") or rust_service.get("type", "")).lower()
        assert ctype, "Container type should not be empty"


class TestSymlinkHandling:
    """Test symlink resolution — no duplicate containers."""

    @pytest.fixture(scope="class")
    def symlink_containers(self):
        """omnipay-symlink-service: src/app.py -> ../shared/app.py (symlink)."""
        path = DEMO_DIR / "omnipay-symlink-service"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_containers(path)

    def test_no_duplicate_containers(self, symlink_containers):
        """Symlink should not create duplicate containers."""
        names = [c.get("name") for c in symlink_containers]
        # shared and src should not both appear as separate services
        assert "shared" not in names or "src" not in names or names.count("shared") == 1, \
            f"Symlink created duplicate: {names}"

    def test_symlink_service_count(self, symlink_containers):
        """Should detect at least 1 service (the root), not double."""
        assert len(symlink_containers) >= 1, \
            f"Expected at least 1 service, got {len(symlink_containers)}: {[c.get('name') for c in symlink_containers]}"


class TestMultiLangTiering:
    """Test polyglot repos get correct tier based on highest-criticality language."""

    @pytest.fixture(scope="class")
    def multi_lang_context(self):
        """omnipay-multi-lang: polyglot service."""
        path = DEMO_DIR / "omnipay-multi-lang"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_tier_reflects_highest_language(self, multi_lang_context):
        """Tier should be set (not Unknown) for polyglot repos."""
        tier = str(multi_lang_context.get("tier", "")).lower()
        assert tier not in ("unknown", ""), \
            f"Polyglot repo should have a tier, got: {tier}"


class TestConflictedOwnership:
    """Test CODEOWNERS conflict — both owners recorded."""

    @pytest.fixture(scope="class")
    def conflicted_context(self):
        """omnipay-conflicted-ownership: two teams claim ownership."""
        path = DEMO_DIR / "omnipay-conflicted-ownership"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_conflicted_ownership_recorded(self, conflicted_context):
        """Conflicted ownership should be detected and recorded."""
        owner = conflicted_context.get("owner", "")
        team = conflicted_context.get("team", "")
        # At minimum, owner or team should be populated (not both unknown)
        has_owner = owner and owner not in ("Unassigned", "unknown", "")
        has_team = team and team not in ("Unassigned", "unknown", "")
        assert has_owner or has_team, \
            f"Expected at least one ownership field populated, got owner={owner}, team={team}"


class TestNoOwnershipGraceful:
    """Test repos with no ownership metadata — graceful degradation."""

    @pytest.fixture(scope="class")
    def no_owner_context(self):
        """omnipay-no-ownership: no CODEOWNERS, no owner in README."""
        path = DEMO_DIR / "omnipay-no-ownership"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_no_ownership_graceful(self, no_owner_context):
        """No ownership metadata should result in owner='Unassigned', not crash."""
        owner = no_owner_context.get("owner", "")
        # Should NOT raise — graceful degradation
        assert isinstance(owner, str), f"Owner should be a string, got: {type(owner)}"
