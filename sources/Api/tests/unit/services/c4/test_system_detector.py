"""Unit tests for SystemDetector actor provenance."""

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
