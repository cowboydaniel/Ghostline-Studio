"""UI for managing installed plugins."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout


class PluginManagerDialog(QDialog):
    def __init__(self, loader, parent=None, category_hint: str | None = None) -> None:
        super().__init__(parent)
        self.loader = loader
        self.category_hint = category_hint
        self.setWindowTitle("Extensions")
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        header = QLabel("Installed plugins" if not category_hint else f"Extensions filtered by {category_hint}")
        layout.addWidget(header)

        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._populate()

    def _populate(self) -> None:
        self.list_widget.clear()
        plugins = self.loader.plugins
        if self.category_hint:
            plugins = [p for p in plugins if self.category_hint.lower() in p.name.lower()]
        for plugin in plugins:
            item = QListWidgetItem(f"{plugin.name}")
            checkbox = QCheckBox("Enabled")
            checkbox.setChecked(plugin.enabled)
            checkbox.stateChanged.connect(lambda state, name=plugin.name: self._toggle(name, state))
            checkbox.setToolTip(self._format_meta(plugin))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)

    def _toggle(self, name: str, state: int) -> None:
        self.loader.set_enabled(name, state == Qt.Checked)

    def _format_meta(self, plugin) -> str:
        meta = []
        if plugin.version:
            meta.append(f"Version: {plugin.version}")
        if plugin.author:
            meta.append(f"Author: {plugin.author}")
        return " | ".join(meta) if meta else ""

