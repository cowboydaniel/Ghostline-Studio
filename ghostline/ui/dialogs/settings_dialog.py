"""Settings dialog exposing a handful of configuration options."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)

from ghostline.core.config import ConfigManager


class SettingsDialog(QDialog):
    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")

        layout = QFormLayout(self)

        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["Ghostline Dark"])
        self.theme_combo.setCurrentText(self.config.get("theme", "Ghostline Dark"))
        layout.addRow("Theme", self.theme_combo)

        self.font_size = QSpinBox(self)
        self.font_size.setRange(8, 32)
        self.font_size.setValue(self.config.get("font", {}).get("editor_size", 11))
        layout.addRow("Editor Font Size", self.font_size)

        self.tab_size = QSpinBox(self)
        self.tab_size.setRange(2, 8)
        self.tab_size.setValue(self.config.get("tabs", {}).get("tab_size", 4))
        layout.addRow("Tab Size", self.tab_size)

        self.use_spaces = QCheckBox("Use spaces for indentation", self)
        self.use_spaces.setChecked(self.config.get("tabs", {}).get("use_spaces", True))
        layout.addRow(self.use_spaces)

        self.autosave = QSpinBox(self)
        self.autosave.setRange(5, 600)
        self.autosave.setValue(self.config.get("autosave", {}).get("interval_seconds", 60))
        layout.addRow("Autosave interval (s)", self.autosave)

        self.lsp_path = QLineEdit(self)
        self.lsp_path.setText(self.config.get("lsp", {}).get("servers", {}).get("python", {}).get("command", "pylsp"))
        layout.addRow("Python LSP", self.lsp_path)

        self.ai_backend = QLineEdit(self)
        self.ai_backend.setText(self.config.get("ai", {}).get("backend", "dummy"))
        layout.addRow("AI Backend", self.ai_backend)

        self.ai_endpoint = QLineEdit(self)
        self.ai_endpoint.setText(self.config.get("ai", {}).get("endpoint", "http://localhost:11434"))
        layout.addRow("AI Endpoint", self.ai_endpoint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _save(self) -> None:
        self.config.settings["theme"] = self.theme_combo.currentText()
        self.config.settings.setdefault("font", {})["editor_size"] = self.font_size.value()
        self.config.settings.setdefault("tabs", {})["tab_size"] = self.tab_size.value()
        self.config.settings.setdefault("tabs", {})["use_spaces"] = self.use_spaces.isChecked()
        self.config.settings.setdefault("autosave", {})["interval_seconds"] = self.autosave.value()
        self.config.settings.setdefault("lsp", {}).setdefault("servers", {}).setdefault("python", {})[
            "command"
        ] = self.lsp_path.text()
        self.config.settings.setdefault("ai", {})["backend"] = self.ai_backend.text()
        self.config.settings.setdefault("ai", {})["endpoint"] = self.ai_endpoint.text()
        self.config.save()
        self.accept()

