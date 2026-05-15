from pathlib import Path
import pytest
from pydantic import ValidationError

from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus, DepEvidence


def test_evidence_corpus_minimal_valid():
    ec = EvidenceCorpus(
        repo_path=Path("/tmp/r"),
        task_id="t1",
        languages=["python"],
        frameworks=["fastapi"],
        deterministic_deps=[],
        entrypoints=[Path("main.py")],
        detected_urls=[],
        env_vars=[],
        docker_images=[],
        package_files=[Path("requirements.txt")],
    )
    assert ec.task_id == "t1"
    assert ec.languages == ["python"]


def test_dep_evidence_requires_confidence_range():
    with pytest.raises(ValidationError):
        DepEvidence(name="x", type="package", confidence=1.5, files_found_in=[])


def test_evidence_corpus_serializable():
    ec = EvidenceCorpus(
        repo_path=Path("/tmp/r"),
        task_id="t1",
        languages=[], frameworks=[], deterministic_deps=[],
        entrypoints=[], detected_urls=[], env_vars=[],
        docker_images=[], package_files=[],
    )
    dumped = ec.model_dump(mode="json")
    assert dumped["task_id"] == "t1"
