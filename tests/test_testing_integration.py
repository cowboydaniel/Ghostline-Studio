from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Signal

from ghostline.semantic.graph import GraphNode, SemanticGraph
from ghostline.semantic.query import SemanticQueryEngine
from ghostline.testing.test_manager import TestManager
from ghostline.testing.test_panel import TestPanel


class DummyTaskManager:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str, str]] = []
        self.output = Signal(str)

    def run_command(self, name: str, command: str, cwd: str = "") -> None:
        self.commands.append((name, command, cwd))


def test_test_manager_builds_commands(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    task_manager = DummyTaskManager()
    manager = TestManager(task_manager, lambda: str(workspace))

    monkeypatch.setattr(shutil, "which", lambda name: "path/to/bin" if name == "pytest" else None)

    states: list[str] = []
    manager.state_changed.connect(states.append)

    manager.run_all()
    assert task_manager.commands[-1] == ("Tests", "pytest", str(workspace))
    assert states[:2] == ["running", "idle"]

    target = workspace / "sample_test.py"
    target.write_text("assert True\n", encoding="utf-8")
    manager.run_file(str(target))
    assert task_manager.commands[-1][1].endswith(target.name)


def test_relevant_tests_uses_semantic_query(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "tests").mkdir()
    semantic_graph = SemanticGraph()
    test_node = GraphNode("feature", "function", workspace / "tests" / "test_feature.py")
    semantic_graph.add_node(test_node)
    query = SemanticQueryEngine(semantic_graph)

    manager = TestManager(DummyTaskManager(), lambda: str(workspace), semantic_query=query)

    relevant = manager.relevant_tests([str(workspace / "feature.py")])
    assert str(test_node.file) in relevant


def test_test_panel_triggers_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    task_manager = DummyTaskManager()
    manager = TestManager(task_manager, lambda: str(workspace))

    editor = type("Editor", (), {"path": workspace / "current.py"})
    panel = TestPanel(manager, lambda: editor)

    panel.run_all.clicked.emit()
    panel.run_file.clicked.emit()

    assert any(cmd[1].startswith("pytest") for cmd in task_manager.commands)

    task_manager.output.emit("hello")
    assert "hello" in panel.output.contents
