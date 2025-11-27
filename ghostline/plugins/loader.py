"""Plugin discovery and loading."""
from __future__ import annotations

import importlib.util
import importlib.abc
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from ghostline.core.config import CONFIG_DIR
from ghostline.plugins.api import PluginContext

PLUGIN_CONFIG_PATH = CONFIG_DIR / "plugins.yaml"


@dataclass
class PluginDefinition:
    name: str
    path: Path
    enabled: bool = True
    version: str | None = None
    author: str | None = None


class PluginLoader:
    """Load user and bundled plugins and manage lifecycle hooks."""

    def __init__(self, app, command_registry, menu_bar, dock_host) -> None:
        self.app = app
        self.command_registry = command_registry
        self.menu_bar = menu_bar
        self.dock_host = dock_host
        self.plugins: list[PluginDefinition] = []
        self.event_bus: dict[str, list[Callable]] = {}
        self._load_enabled_state()

    def discover(self) -> None:
        self.plugins = []
        user_dir = CONFIG_DIR / "plugins"
        bundled_dir = Path(__file__).parent / "builtins"
        for base in (bundled_dir, user_dir):
            if not base.exists():
                continue
            for path in base.glob("*.py"):
                self._register_plugin(path)

    def _register_plugin(self, path: Path) -> None:
        name = path.stem
        enabled = self.enabled_state.get(name, True)
        metadata_path = path.with_suffix("").with_name("plugin.yaml")
        metadata = yaml.safe_load(metadata_path.read_text()) if metadata_path.exists() else {}
        definition = PluginDefinition(
            name=name,
            path=path,
            enabled=enabled,
            version=metadata.get("version") if isinstance(metadata, dict) else None,
            author=metadata.get("author") if isinstance(metadata, dict) else None,
        )
        self.plugins.append(definition)

    def load_all(self) -> None:
        self.discover()
        for plugin in self.plugins:
            if plugin.enabled:
                self._load_plugin(plugin)

    def _load_plugin(self, plugin: PluginDefinition) -> None:
        spec = importlib.util.spec_from_file_location(plugin.name, plugin.path)
        if not spec or not spec.loader:
            return
        module = importlib.util.module_from_spec(spec)
        loader = spec.loader
        assert isinstance(loader, importlib.abc.Loader)  # type: ignore[attr-defined]
        loader.exec_module(module)  # type: ignore[arg-type]
        self._run_register(module, plugin)

    def _run_register(self, module: types.ModuleType, plugin: PluginDefinition) -> None:
        register_fn = getattr(module, "register", None)
        if not register_fn:
            return
        context = PluginContext(
            self.app,
            self.command_registry,
            self.menu_bar,
            self.dock_host,
            self.event_bus,
        )
        register_fn(context)
        plugin.version = getattr(module, "__version__", None)
        plugin.author = getattr(module, "__author__", None)

    def save_state(self) -> None:
        PLUGIN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = {plugin.name: plugin.enabled for plugin in self.plugins}
        with PLUGIN_CONFIG_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(state, handle)

    def set_enabled(self, name: str, enabled: bool) -> None:
        for plugin in self.plugins:
            if plugin.name == name:
                plugin.enabled = enabled
        self.save_state()

    def emit_event(self, event_name: str, **payload) -> None:
        for callback in self.event_bus.get(event_name, []):
            callback(payload)

    def _load_enabled_state(self) -> None:
        if PLUGIN_CONFIG_PATH.exists():
            self.enabled_state = yaml.safe_load(PLUGIN_CONFIG_PATH.read_text()) or {}
        else:
            self.enabled_state = {}

