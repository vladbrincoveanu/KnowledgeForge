"""Unit tests for SystemDetector actor provenance."""

import pytest
from app.services.c4.context.system_detector import SystemDetector


class TestSystemDetectorActors:
    """Verify actor extraction keeps provenance for human review."""

    def test_detect_context_actors_captures_heading_source_and_evidence(self, tmp_path):
        (tmp_path / "README.md").write_text(
            "# Fraud Analyst\n"
            "Reviews flagged transactions and feeds labels back into the model.\n",
            encoding="utf-8",
        )

        detector = SystemDetector(tmp_path)
        actors = detector.detect_context_actors()

        assert actors == [
            {
                "name": "Fraud Analyst",
                "type": "person",
                "description": "Reviews flagged transactions and feeds labels back into the model.",
                "detected_from": "README.md",
                "detection_method": "documentation_heading",
                "evidence": "# Fraud Analyst",
            }
        ]

    def test_detect_context_actors_excludes_step_headings(self, tmp_path):
        (tmp_path / "README.md").write_text(
            "# Step 2.5: Setup User\n"
            "Configure the initial admin account.\n",
            encoding="utf-8",
        )
        detector = SystemDetector(tmp_path)
        actors = detector.detect_context_actors()
        step_actors = [a for a in actors if "Step" in a.get("evidence", "") or "Step" in a.get("name", "")]
        assert step_actors == [], f"Step heading should not produce actors: {step_actors}"

    def test_detect_frameworks_pyproject_structural_no_false_positive(self, tmp_path):
        pyproject = """
[project]
name = "my-project"
dependencies = ["fastapi>=0.100.0"]

[project.optional-dependencies]
dev = ["django-stubs>=4.0", "pytest-django>=4.5"]
"""
        (tmp_path / "pyproject.toml").write_text(pyproject)
        detector = SystemDetector(tmp_path)
        frameworks = detector.detect_frameworks()
        django_names = [f["name"] for f in frameworks if "django" in f["name"].lower()]
        assert django_names == [], f"Django false positive: {django_names}"
