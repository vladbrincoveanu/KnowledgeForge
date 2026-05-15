import json
from pathlib import Path
from typing import Any


class EnrichmentJSONPersister:
    def __init__(self, base_dir: Path, task_id: str, run_id: str):
        self.base_dir = Path(base_dir)
        self.task_id = task_id
        self.run_id = run_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.base_dir / f"{task_id}.jsonl"
        self.json_path = self.base_dir / f"{task_id}.json"
        self._events: list[dict[str, Any]] = []

    def append(self, event: dict[str, Any]) -> None:
        event = {**event, "run_id": self.run_id}
        self._events.append(event)
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def finalize(self, summary: dict[str, Any]) -> None:
        snapshot = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "summary": summary,
            "events": self._events,
        }
        self.json_path.write_text(json.dumps(snapshot, indent=2, default=str))

    def rollback(self) -> None:
        for p in (self.jsonl_path, self.json_path):
            if p.exists():
                p.unlink()