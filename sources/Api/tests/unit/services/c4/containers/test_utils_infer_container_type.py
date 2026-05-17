"""Regression tests for utils.infer_container_type.

These lock in the post-fix contract:
  1. Dependency manifests (package.json, pyproject.toml) take priority over
     Dockerfile keyword presence — a Dockerfile mentioning `node` does NOT
     by itself mean the project is a frontend.
  2. Every value returned must be in llm_enrichment._GENERIC_CONTAINER_TYPES
     so the LLM enrichment pass is allowed to refine it. Without this
     contract, mis-classifications get permanently locked in.
"""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.c4.containers.utils import infer_container_type
from app.services.c4.containers.llm_enrichment import _GENERIC_CONTAINER_TYPES


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def _write_pkg(project_dir: Path, deps=None, dev_deps=None, scripts=None):
    payload = {"name": "x", "version": "1.0.0"}
    if deps is not None:
        payload["dependencies"] = deps
    if dev_deps is not None:
        payload["devDependencies"] = dev_deps
    if scripts is not None:
        payload["scripts"] = scripts
    (project_dir / "package.json").write_text(json.dumps(payload))


def _write_dockerfile(project_dir: Path, body: str):
    (project_dir / "Dockerfile").write_text(body)


class TestPriorityOverDockerfile:
    """Dependency-manifest signal must beat Dockerfile keyword presence."""

    def test_express_backend_with_node_dockerfile_is_not_frontend(self, project_dir):
        _write_pkg(project_dir, deps={"express": "^4.18.0", "pg": "^8.0.0"},
                   scripts={"start": "node server.js"})
        _write_dockerfile(project_dir,
                          'FROM node:20-alpine\nCMD ["node", "server.js"]\n')
        result = infer_container_type(project_dir)
        assert result == "Node.js Service"
        assert "Frontend" not in result, (
            "Backend Express service must not be labeled Frontend just "
            "because the Dockerfile uses node base image"
        )

    def test_react_app_classified_as_frontend(self, project_dir):
        _write_pkg(project_dir,
                   deps={"react": "^18.0.0", "react-dom": "^18.0.0"},
                   dev_deps={"vite": "^5.0.0"})
        result = infer_container_type(project_dir)
        assert result == "Frontend Application"

    def test_python_fastapi_recognized(self, project_dir):
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "api"\ndependencies = ["fastapi>=0.100"]\n'
        )
        result = infer_container_type(project_dir)
        assert result == "Python Service"

    def test_python_no_framework_is_generic(self, project_dir):
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "lib"\ndependencies = ["numpy"]\n'
        )
        result = infer_container_type(project_dir)
        assert result == "Python Application"

    def test_dockerfile_only_falls_through(self, project_dir):
        _write_dockerfile(project_dir, "FROM alpine\nRUN apk add curl\n")
        assert infer_container_type(project_dir) == "Containerized Service"

    def test_empty_directory(self, project_dir):
        assert infer_container_type(project_dir) == "Service"


class TestLlmOverridability:
    """Every value the rule-based classifier emits must be overridable by the
    LLM enrichment pass — otherwise mis-classifications get permanently
    locked in (the original 'Frontend (Node.js)' bug)."""

    def test_node_outputs_are_llm_overridable(self, project_dir):
        # Cover all branches that emit a Node-related label
        for deps, expected in [
            ({"react": "^18.0.0"}, "Frontend Application"),
            ({"express": "^4.18.0"}, "Node.js Service"),
            ({"lodash": "^4.0.0"}, "Node.js Application"),  # no framework, no start script
        ]:
            _write_pkg(project_dir, deps=deps)
            assert infer_container_type(project_dir) in _GENERIC_CONTAINER_TYPES, (
                f"deps={deps} produced non-overridable label"
            )

    def test_python_outputs_are_llm_overridable(self, project_dir):
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["fastapi"]\n'
        )
        assert infer_container_type(project_dir) in _GENERIC_CONTAINER_TYPES

    def test_jvm_go_rust_outputs_are_llm_overridable(self, project_dir):
        for filename in ("pom.xml", "go.mod", "Cargo.toml"):
            target = project_dir / filename
            target.write_text("// stub")
            assert infer_container_type(project_dir) in _GENERIC_CONTAINER_TYPES, (
                f"{filename} produced non-overridable label"
            )
            target.unlink()

    def test_dockerfile_only_output_is_llm_overridable(self, project_dir):
        _write_dockerfile(project_dir, "FROM alpine")
        assert infer_container_type(project_dir) in _GENERIC_CONTAINER_TYPES

    def test_empty_output_is_llm_overridable(self, project_dir):
        assert infer_container_type(project_dir) in _GENERIC_CONTAINER_TYPES
