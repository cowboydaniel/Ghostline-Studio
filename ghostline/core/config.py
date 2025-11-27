"""Configuration management for Ghostline Studio."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    import json

    class _YamlShim:
        @staticmethod
        def safe_load(stream):
            text = stream.read() if hasattr(stream, "read") else stream
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {}

        @staticmethod
        def safe_dump(data, stream):
            stream.write(json.dumps(data))

    yaml = _YamlShim()

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ghostline"
DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "settings" / "defaults.yaml"
USER_SETTINGS_PATH = CONFIG_DIR / "settings.yaml"
WORKSPACE_MEMORY_PATH = CONFIG_DIR / "workspace_memory.json"


class ConfigManager:
    """Loads default and user configuration and provides helpers to query values."""

    def __init__(self) -> None:
        self.defaults = self._load_yaml(DEFAULTS_PATH)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if USER_SETTINGS_PATH.exists():
            self.user_settings = self._load_yaml(USER_SETTINGS_PATH)
        else:
            self.user_settings = {}
        self.settings = self._deep_merge(self.defaults, self.user_settings)
        self.workspace_memory_path = Path(self.settings.get("workspace_memory_path", WORKSPACE_MEMORY_PATH))

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value

    def path_for(self, key: str, fallback: Path) -> Path:
        value = self.settings.get(key)
        return Path(value) if value else fallback

    def save(self) -> None:
        USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with USER_SETTINGS_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(self.settings, handle)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = dict(base)
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def self_healing_enabled(self) -> bool:
        """Flag for enabling the self-healing service."""

        return bool(self.settings.get("self_healing", {}).get("enabled", True))
