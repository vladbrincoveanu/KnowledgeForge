from unittest.mock import MagicMock
import pytest
from app.services.c4.enrichment.graph_writer import (
    EnrichmentGraphWriter, normalize_logical_name,
)


def test_normalize_strips_scheme_and_suffix():
    assert normalize_logical_name("https://api.Stripe.com/v1") == "stripe"
    assert normalize_logical_name("Stripe-API") == "stripe"
    assert normalize_logical_name("Datadog SDK") == "datadog"


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def writer(mock_session):
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = mock_session
    return EnrichmentGraphWriter(driver=driver, task_id="t1", run_id="r1")


def test_upsert_node_runs_merge_with_canonical(writer, mock_session):
    writer.upsert_node(
        type_="external_dep", name="Stripe",
        props={"confidence": 0.8, "evidence": [{"file": "a.py", "line": 1}]},
    )
    args, kwargs = mock_session.run.call_args
    assert "MERGE" in args[0]
    assert kwargs["canonical"] == "stripe"
    assert kwargs["name"] == "Stripe"
    assert kwargs["run_id"] == "r1"


def test_upsert_edge_includes_run_id(writer, mock_session):
    writer.upsert_edge(from_name="Sys", to_name="Stripe",
                       relationship="uses", props={})
    args, kwargs = mock_session.run.call_args
    assert kwargs["run_id"] == "r1"


def test_rollback_deletes_by_run_id(writer, mock_session):
    writer.rollback()
    args, _ = mock_session.run.call_args
    assert "DETACH DELETE" in args[0]
    assert "enrichment_run_id" in args[0]
