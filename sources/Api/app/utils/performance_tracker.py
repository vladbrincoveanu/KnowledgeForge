"""Performance tracking for extraction pipeline benchmarking."""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TimingResult:
    name: str
    duration_ms: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class BenchmarkResults:
    task_id: str
    repository_url: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_duration_ms: float = 0.0
    phases: list[TimingResult] = field(default_factory=list)
    sub_phases: dict[str, list[TimingResult]] = field(default_factory=dict)

    def add_phase(self, name: str, duration_ms: float, success: bool = True, error: Optional[str] = None):
        self.phases.append(TimingResult(name=name, duration_ms=duration_ms, success=success, error=error))
        self.total_duration_ms += duration_ms

    def add_sub_phase(self, parent: str, name: str, duration_ms: float, success: bool = True, error: Optional[str] = None):
        if parent not in self.sub_phases:
            self.sub_phases[parent] = []
        self.sub_phases[parent].append(TimingResult(name=name, duration_ms=duration_ms, success=success, error=error))

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{self.task_id}_benchmark.json"
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return filepath


class PerformanceTracker:
    def __init__(self, task_id: str, repository_url: str, output_dir: Optional[Path] = None):
        self.task_id = task_id
        self.repository_url = repository_url
        self.results = BenchmarkResults(task_id=task_id, repository_url=repository_url)
        self.output_dir = output_dir or Path("sources/data/benchmarks")
        self._phase_stack: list[tuple[str, float]] = []

    def start_phase(self, name: str):
        self._phase_stack.append((name, time.time()))

    def end_phase(self, name: str, success: bool = True, error: Optional[str] = None):
        if not self._phase_stack or self._phase_stack[-1][0] != name:
            raise ValueError(f"Phase '{name}' was not started")
        _, start_time = self._phase_stack.pop()
        duration_ms = (time.time() - start_time) * 1000
        self.results.add_phase(name, duration_ms, success, error)
        return duration_ms

    def time_block(self, name: str):
        return _TimeBlock(self, name)

    def save(self) -> Path:
        return self.results.save(self.output_dir)

    def get_summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "total_duration_ms": self.results.total_duration_ms,
            "phase_count": len(self.results.phases),
            "phases": [(p.name, p.duration_ms) for p in self.results.phases],
        }


class _TimeBlock:
    def __init__(self, tracker: PerformanceTracker, name: str):
        self.tracker = tracker
        self.name = name
        self._start_time: Optional[float] = None
        self._duration_ms: Optional[float] = None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is not None:
            self._duration_ms = (time.time() - self._start_time) * 1000
            self.tracker.results.add_phase(
                self.name,
                self._duration_ms,
                success=exc_type is None,
                error=str(exc_val) if exc_type else None
            )
        return False
