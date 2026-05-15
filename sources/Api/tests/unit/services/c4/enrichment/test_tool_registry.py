from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.services.c4.enrichment.tool_registry import ExtractionToolRegistry


@pytest.fixture
def mock_writer():
    w = MagicMock()
    return w


@pytest.fixture
def mock_persister():
    p = MagicMock()
    return p


def test_grep_returns_matches(tmp_path):
    (tmp_path / "main.py").write_text("import stripe\nimport redis")
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=MagicMock(),
        persister=MagicMock(), ws_emit=MagicMock(),
    )
    result = registry.grep("import.*stripe", path=".")
    assert len(result) == 1
    assert "stripe" in result[0]["snippet"]


def test_read_file_returns_content(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=MagicMock(),
        persister=MagicMock(), ws_emit=MagicMock(),
    )
    result = registry.read_file("main.py")
    assert "hello" in result["content"]


def test_list_dir_returns_files(tmp_path):
    (tmp_path / "a.py").write_text("x=1")
    (tmp_path / "b.py").write_text("y=2")
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=MagicMock(),
        persister=MagicMock(), ws_emit=MagicMock(),
    )
    result = registry.list_dir(str(tmp_path))
    assert len(result) == 2


def test_emit_node_calls_writer_and_persister(mock_writer, mock_persister, tmp_path):
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=mock_writer,
        persister=mock_persister, ws_emit=MagicMock(),
    )
    registry.emit_node(type_="external_dep", name="Stripe",
                       props={"confidence": 0.9})
    mock_writer.upsert_node.assert_called_once()
    mock_persister.append.assert_called_once()


def test_emit_edge_calls_writer(mock_writer, mock_persister, tmp_path):
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=mock_writer,
        persister=mock_persister, ws_emit=MagicMock(),
    )
    registry.emit_edge(from_name="Sys", to_name="Stripe",
                       relationship="uses", props={})
    mock_writer.upsert_edge.assert_called_once()


def test_tools_return_expected_structure(tmp_path):
    registry = ExtractionToolRegistry(
        repo_path=tmp_path, graph_writer=MagicMock(),
        persister=MagicMock(), ws_emit=MagicMock(),
    )
    tools = registry.get_tools()
    names = [t["name"] for t in tools]
    assert set(names) == {"grep", "read_file", "list_dir", "emit_node", "emit_edge"}