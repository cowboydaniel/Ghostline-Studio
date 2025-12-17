"""Simple management helpers for ghostline_launch.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_LAUNCH_CONTENT = {
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "args": [],
            "cwd": "${workspaceFolder}",
        }
    ],
}


@dataclass
class LaunchConfiguration:
    name: str
    program: str
    args: list[str]
    cwd: str | None = None


class LaunchConfigurationManager:
    """Read and write ghostline_launch.json files in the workspace."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root

    def set_workspace(self, workspace: Path | None) -> None:
        self.workspace_root = workspace

    def config_path(self) -> Path | None:
        if not self.workspace_root:
            return None
        return self.workspace_root / "ghostline_launch.json"

    def ensure_file(self) -> Path | None:
        path = self.config_path()
        if not path:
            return None
        if not path.exists():
            path.write_text(json.dumps(DEFAULT_LAUNCH_CONTENT, indent=2))
        return path

    def load(self) -> dict:
        path = self.ensure_file()
        if not path:
            return DEFAULT_LAUNCH_CONTENT.copy()
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return DEFAULT_LAUNCH_CONTENT.copy()

    def list_configurations(self) -> list[LaunchConfiguration]:
        data = self.load()
        configs: Iterable[dict] = data.get("configurations", []) if isinstance(data, dict) else []
        parsed: list[LaunchConfiguration] = []
        for entry in configs:
            if not isinstance(entry, dict):
                continue
            program = entry.get("program")
            name = entry.get("name")
            if not program or not name:
                continue
            parsed.append(
                LaunchConfiguration(
                    name=name,
                    program=program,
                    args=list(entry.get("args", [])) if isinstance(entry.get("args", []), list) else [],
                    cwd=entry.get("cwd"),
                )
            )
        return parsed

    def add_configuration(self, config: dict) -> None:
        path = self.ensure_file()
        if not path:
            return
        data = self.load()
        configs = data.get("configurations") if isinstance(data, dict) else None
        if not isinstance(configs, list):
            configs = []
        configs.append(config)
        data["configurations"] = configs
        path.write_text(json.dumps(data, indent=2))

    def resolve_configuration(
        self, name: str | None, current_file: Path | None
    ) -> LaunchConfiguration | None:
        configs = self.list_configurations()
        selected = None
        if name:
            for cfg in configs:
                if cfg.name == name:
                    selected = cfg
                    break
        if not selected and configs:
            selected = configs[0]
        if not selected:
            return None
        # Replace tokens with actual paths
        program = self._substitute(selected.program, current_file)
        cwd = self._substitute(selected.cwd, current_file) if selected.cwd else None
        return LaunchConfiguration(name=selected.name, program=program, args=selected.args, cwd=cwd)

    def _substitute(self, value: str, current_file: Path | None) -> str:
        workspace = str(self.workspace_root) if self.workspace_root else ""
        file_path = str(current_file) if current_file else ""
        substitutions = {
            "${workspaceFolder}": workspace,
            "${file}": file_path,
        }
        result = value
        for token, replacement in substitutions.items():
            result = result.replace(token, replacement)
        return result
