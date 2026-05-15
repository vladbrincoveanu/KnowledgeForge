from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.c4.context.context_manager import ContextManager


def test_extract_context_enqueues_worker(tmp_path):
    (tmp_path / "main.py").write_text("print(1)")
    with patch("app.domain.review_queue.enqueue_review_item", return_value=None):
        mgr = ContextManager(repo_path=tmp_path, task_id="t1")
    with patch("app.services.c4.enrichment.worker.enqueue") as enq, \
         patch("app.domain.review_queue.enqueue_review_item", return_value=None):
        ctx = mgr.extract_context()
    assert "name" in ctx
    enq.assert_called_once()
    kwargs = enq.call_args.kwargs or {}
    args = enq.call_args.args
    assert len(args) + len(kwargs) == 3


def test_extract_context_does_not_block_on_worker(tmp_path):
    (tmp_path / "main.py").write_text("print(1)")
    with patch("app.domain.review_queue.enqueue_review_item", return_value=None):
        mgr = ContextManager(repo_path=tmp_path)
    with patch("app.services.c4.enrichment.worker.enqueue") as enq, \
         patch("app.domain.review_queue.enqueue_review_item", return_value=None):
        ctx = mgr.extract_context()
    assert ctx is not None