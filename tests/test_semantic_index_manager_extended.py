from __future__ import annotations

from pathlib import Path

from ghostline.semantic.graph import GraphNode
from ghostline.semantic.index_manager import SemanticIndexManager


class ImmediateWorkers:
    def __init__(self) -> None:
        self.jobs: dict[str, tuple[callable, Path]] = {}

    def submit(self, key: str, func, *args, **kwargs):
        self.jobs[key] = (func, args[0] if args else None)
        return func(*args, **kwargs)

    def shutdown(self) -> None:  # pragma: no cover - API compatibility
        self.jobs.clear()


def _write_sample_file(path: Path) -> None:
    path.write_text(
        """
import math

class Demo:
    def method(self):
        return math.sqrt(4)

def helper(x):
    return x * 2
""",
        encoding="utf-8",
    )


def test_reindex_and_recent_paths(tmp_path: Path) -> None:
    _write_sample_file(tmp_path / "module.py")
    notifications: list[Path] = []

    manager = SemanticIndexManager(lambda: str(tmp_path), workers=ImmediateWorkers())
    manager.register_observer(lambda path: notifications.append(path))
    manager.reindex()

    names = {node.name for node in manager.graph.nodes()}
    assert {"Demo", "helper", "module"}.issubset(names)
    assert notifications[-1] == tmp_path

    snapshot = manager.get_graph_snapshot()
    assert any(entry["type"] == "class" for entry in snapshot["nodes"])


def test_remove_file_prunes_nodes(tmp_path: Path) -> None:
    file_path = tmp_path / "old.py"
    _write_sample_file(file_path)

    manager = SemanticIndexManager(lambda: str(tmp_path), workers=ImmediateWorkers())
    manager.reindex()
    manager._remove_file(file_path)

    assert all(node.file != file_path for node in manager.graph.nodes())


def test_record_runtime_event_updates_hotspots(tmp_path: Path) -> None:
    file_path = tmp_path / "runtime.py"
    file_path.write_text("def sample():\n    return True\n", encoding="utf-8")

    manager = SemanticIndexManager(lambda: str(tmp_path), workers=ImmediateWorkers())
    manager.reindex()

    observations: list[Path] = []
    manager.register_observer(lambda path: observations.append(path))

    observation = type("Obs", (), {"path": str(file_path), "calls": ["sample"]})
    manager.record_runtime_event(observation)

    assert GraphNode("sample", "function", file_path) in manager.graph.nodes()
    assert observations[-1] == file_path
