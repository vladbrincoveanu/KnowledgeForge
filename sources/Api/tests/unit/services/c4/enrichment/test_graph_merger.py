from unittest.mock import MagicMock
import pytest
from app.services.c4.enrichment.graph_merger import GraphMerger
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus


def test_merge_adds_llm_nodes(tmp_path):
    writer = MagicMock()
    persister = MagicMock()
    ec = EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                       languages=[], frameworks=[], deterministic_deps=[],
                       entrypoints=[], detected_urls=[], env_vars=[],
                       docker_images=[], package_files=[])
    merger = GraphMerger(evidence=ec, writer=writer, persister=persister)
    merger.add_node(type_="external_dep", name="Stripe",
                    props={"confidence": 0.9, "evidence": []})
    writer.upsert_node.assert_called()


def test_finalize_calls_persister_finalize(tmp_path):
    writer = MagicMock()
    persister = MagicMock()
    ec = EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                       languages=[], frameworks=[], deterministic_deps=[],
                       entrypoints=[], detected_urls=[], env_vars=[],
                       docker_images=[], package_files=[])
    merger = GraphMerger(evidence=ec, writer=writer, persister=persister)
    merger.finalize({"nodes_added": 5, "partial": False})
    persister.finalize.assert_called_once()


def test_rollback_calls_writer_rollback(tmp_path):
    writer = MagicMock()
    persister = MagicMock()
    ec = EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                       languages=[], frameworks=[], deterministic_deps=[],
                       entrypoints=[], detected_urls=[], env_vars=[],
                       docker_images=[], package_files=[])
    merger = GraphMerger(evidence=ec, writer=writer, persister=persister)
    merger.rollback()
    writer.rollback.assert_called_once()
    persister.rollback.assert_called_once()