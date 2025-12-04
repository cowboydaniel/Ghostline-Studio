from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import ghostline.core.config as config_mod
from ghostline.ai.ai_client import AIResponse
from ghostline.ai.analysis_service import AnalysisService
from ghostline.build.build_manager import BuildManager
from ghostline.core.cache import CacheManager, FileSignatureCache
from ghostline.core.events import CommandDescriptor, CommandRegistry
from ghostline.core.self_healing import SelfHealingService
from ghostline.ui.status_bar import StudioStatusBar
from ghostline.vcs.git_integration import GitIntegration


@pytest.fixture(scope="session")
def ensure_qt_app(qt_app: QApplication | None):
    # Ensure widgets can be instantiated even in headless environments
    try:
        return qt_app or QApplication.instance() or QApplication([])
    except AttributeError:
        return qt_app or QApplication([])


def test_cache_manager_refreshes_and_expires(monkeypatch) -> None:
    cache = CacheManager()

    cache.set("alpha", "value", ttl=0)
    # Force the timestamp to appear old
    cache._entries["alpha"].timestamp = 0.0
    monkeypatch.setattr("ghostline.core.cache.time.time", lambda: 10.0)
    assert cache.get("alpha") is None

    refreshed = cache.get("alpha", factory=lambda: "fresh", ttl=1)
    assert refreshed == "fresh"


def test_file_signature_cache_tracks_changes(tmp_path: Path) -> None:
    file_path = tmp_path / "demo.txt"
    file_path.write_text("one", encoding="utf-8")

    cache = FileSignatureCache(tmp_path)
    first = cache.signature(file_path)
    time.sleep(0.05)
    file_path.write_text("two", encoding="utf-8")
    current = file_path.stat()
    os.utime(file_path, (current.st_atime, current.st_mtime + 1))
    cache._entries[str(file_path)].ttl = 0
    cache._entries[str(file_path)].timestamp = 0
    second = cache.signature(file_path)

    assert first != second


def test_config_manager_uses_user_settings(monkeypatch, tmp_path: Path) -> None:
    # Redirect config paths to an isolated temp directory
    config_root = tmp_path / "config"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_root)
    monkeypatch.setattr(config_mod, "USER_SETTINGS_PATH", config_root / "settings.yaml")
    monkeypatch.setattr(config_mod, "WORKSPACE_MEMORY_PATH", config_root / "workspace_memory.json")

    manager = config_mod.ConfigManager()
    manager.set("example", 42)
    manager.save()

    reloaded = config_mod.ConfigManager()
    assert reloaded.get("example") == 42
    assert config_mod.USER_SETTINGS_PATH.exists()


def test_self_healing_reports_missing_tools(tmp_path: Path) -> None:
    class DummyConfig:
        def __init__(self) -> None:
            self.settings = {"formatter": {"line_length": 0}, "lsp": {"servers": {}}}

        def get(self, key: str, default=None):  # noqa: ANN001
            return self.settings.get(key, default)

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    service = SelfHealingService(DummyConfig(), lambda: str(workspace))
    emissions: list[list] = []
    service.issues_changed.connect(emissions.append)

    service.scan()

    assert len(service.issues) == 3
    assert len(emissions) == 1
    assert all(issue.suggested_fix for issue in service.issues)


def test_command_registry_filters_commands() -> None:
    registry = CommandRegistry()

    registry.register_command(CommandDescriptor("format", "Format file", "edit", lambda: None))
    registry.register_command(CommandDescriptor("format", "Format file", "edit", lambda: None))
    registry.register_command(CommandDescriptor("test", "Run tests", "tasks", lambda: None))

    all_cmds = registry.list_commands()
    assert len(all_cmds) == 2

    filtered = registry.list_commands("test")
    assert {cmd.id for cmd in filtered} == {"test"}


def test_build_manager_runs_tasks(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outputs: list[tuple[str, str]] = []
    finished: list[tuple[str, int]] = []
    states: list[str] = []

    class FakeProcess:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            self.stdout = ["hello\n"]

        def wait(self) -> int:
            return 0

        def terminate(self) -> None:
            return None

    class ImmediateThread:
        def __init__(self, target, args=(), kwargs=None, daemon=None):  # noqa: ANN001,ANN002,ANN003
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self) -> None:
            self._target(*self._args, **self._kwargs)

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    manager = BuildManager(lambda: str(workspace))
    manager.task_output.connect(lambda name, line: outputs.append((name, line)))
    manager.task_finished.connect(lambda name, code: finished.append((name, code)))
    manager.state_changed.connect(states.append)

    manager.register_task("build", "echo ok")
    manager.enqueue_all()

    assert outputs and outputs[0][1] == "hello"
    assert finished == [("build", 0)]
    assert states[-1] == "idle"
    assert manager.recent_results()["build"] == 0


def test_git_integration_subprocess_calls(monkeypatch, tmp_path: Path) -> None:
    class Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    runs: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        runs.append(cmd)
        if "rev-parse" in cmd:
            return Result("main\n")
        return Result("M file.py\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    git = GitIntegration()
    assert git.branch_name(str(tmp_path)) == "main"
    assert git.is_dirty(str(tmp_path))
    assert any("rev-parse" in cmd for cmd in runs)


def test_status_bar_updates_labels(ensure_qt_app) -> None:
    class DummyGit(GitIntegration):
        def branch_name(self, path):  # noqa: ANN001
            return "main"

        def is_dirty(self, path):  # noqa: ANN001
            return True

    bar = StudioStatusBar(DummyGit())
    bar.show_path("/tmp/project")
    bar.set_ai_suggestions_available(True)
    bar.show_predicted_actions(["build"])
    bar.update_git("/tmp/project")

    assert bar.path_label.text() == "/tmp/project"
    assert "AI suggestions" in bar.ai_label.text()
    assert bar.prediction_label.text().startswith("Next:")
    assert bar.git_label.text() == "main*"


def test_analysis_service_accumulates_suggestions(ensure_qt_app) -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.prompts: list[tuple[str, str]] = []

        def send(self, prompt: str, context: str | None = None) -> AIResponse:
            self.prompts.append((prompt, context or ""))
            return AIResponse(text="ok")

    class ImmediateWorkers:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def submit(self, key: str, func, *args, **kwargs):  # noqa: ANN001,ANN002,ANN003
            self.calls.append(key)
            return func(*args, **kwargs)

    class Emitter(QObject):
        state_changed = Signal(str)

    client = DummyClient()
    service = AnalysisService(client, workers=ImmediateWorkers())
    emissions: list[list] = []
    service.suggestions_changed.connect(emissions.append)

    service.on_file_saved("file.py", "print('hi')")
    assert emissions[-1][0].detail == "ok"

    emitter = Emitter()
    service.bind_build_manager(emitter)
    emitter.state_changed.emit("running")

    assert any("Process state change" in s.title for s in service.suggestions())
    assert client.prompts
