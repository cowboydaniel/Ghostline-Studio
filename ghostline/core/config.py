"""Configuration management for Ghostline Studio."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ghostline"
DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "settings" / "defaults.yaml"
USER_SETTINGS_PATH = CONFIG_DIR / "settings.yaml"


class ConfigManager:
    """Loads default and user configuration and provides helpers to query values."""

    def __init__(self) -> None:
        self.defaults = self._load_yaml(DEFAULTS_PATH)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if USER_SETTINGS_PATH.exists():
            self.user_settings = self._load_yaml(USER_SETTINGS_PATH)
        else:
            self.user_settings = {}
        self.settings = {**self.defaults, **self.user_settings}

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value

    def save(self) -> None:
        USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with USER_SETTINGS_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(self.settings, handle)
