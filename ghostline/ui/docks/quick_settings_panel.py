"""Quick Settings Panel for Ghostline Studio."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QLabel,
    QPushButton,
    QHBoxLayout,
)

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager

logger = logging.getLogger(__name__)


class QuickSettingsPanel(QWidget):
    """Quick access settings panel with real-time updates."""

    def __init__(self, config: ConfigManager, theme_manager: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.theme_manager = theme_manager
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Build the quick settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("Quick Settings")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Settings form
        form = QFormLayout()
        form.setSpacing(8)

        # Theme selector
        self.theme_combo = QComboBox()
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow("Theme:", self.theme_combo)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(32)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        form.addRow("Font Size:", self.font_size_spin)

        # Tab size
        self.tab_size_spin = QSpinBox()
        self.tab_size_spin.setMinimum(1)
        self.tab_size_spin.setMaximum(8)
        self.tab_size_spin.valueChanged.connect(self._on_tab_size_changed)
        form.addRow("Tab Size:", self.tab_size_spin)

        # Word wrap
        self.word_wrap_check = QCheckBox("Enable Word Wrap")
        self.word_wrap_check.toggled.connect(self._on_word_wrap_changed)
        form.addRow("", self.word_wrap_check)

        # Autosave
        self.autosave_check = QCheckBox("Enable Autosave")
        self.autosave_check.toggled.connect(self._on_autosave_changed)
        form.addRow("", self.autosave_check)

        self.autosave_interval_spin = QSpinBox()
        self.autosave_interval_spin.setMinimum(500)
        self.autosave_interval_spin.setMaximum(60000)
        self.autosave_interval_spin.setSingleStep(500)
        self.autosave_interval_spin.setSuffix(" ms")
        self.autosave_interval_spin.valueChanged.connect(self._on_autosave_interval_changed)
        form.addRow("Autosave Interval:", self.autosave_interval_spin)

        layout.addLayout(form)

        # AI Backend (if applicable)
        ai_cfg = self.config.get("ai", {})
        if isinstance(ai_cfg, dict):
            ai_backend_label = QLabel("AI Backend")
            ai_backend_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 10px;")
            layout.addWidget(ai_backend_label)

            ai_form = QFormLayout()

            self.ai_backend_combo = QComboBox()
            self.ai_backend_combo.addItems(["OpenAI", "Ollama"])
            current_provider = ai_cfg.get("provider", "openai")
            index = 1 if current_provider.lower() == "ollama" else 0
            self.ai_backend_combo.setCurrentIndex(index)
            self.ai_backend_combo.currentTextChanged.connect(self._on_ai_backend_changed)
            ai_form.addRow("Provider:", self.ai_backend_combo)

            self.ai_endpoint_input = QComboBox()
            if current_provider.lower() == "openai":
                self.ai_endpoint_input.addItem("https://api.openai.com/v1")
            else:
                self.ai_endpoint_input.addItem(ai_cfg.get("base_url", "http://localhost:11434"))
            self.ai_endpoint_input.setEditable(True)
            self.ai_endpoint_input.currentTextChanged.connect(self._on_ai_endpoint_changed)
            ai_form.addRow("Endpoint:", self.ai_endpoint_input)

            layout.addLayout(ai_form)

        layout.addStretch()

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._on_reset_defaults)
        layout.addWidget(reset_btn)

    def _load_settings(self) -> None:
        """Load current settings from config."""
        # Theme
        available_themes = self.theme_manager.get_available_themes()
        self.theme_combo.addItems(available_themes)
        current_theme = self.config.get("theme", "dark")
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        # Font size
        font_cfg = self.config.get("font", {})
        font_size = font_cfg.get("size", 11) if isinstance(font_cfg, dict) else 11
        self.font_size_spin.setValue(font_size)

        # Tab size
        tabs_cfg = self.config.get("tabs", {})
        tab_size = tabs_cfg.get("size", 4) if isinstance(tabs_cfg, dict) else 4
        self.tab_size_spin.setValue(tab_size)

        # Word wrap
        editor_cfg = self.config.get("editor", {})
        word_wrap = editor_cfg.get("word_wrap", False) if isinstance(editor_cfg, dict) else False
        self.word_wrap_check.setChecked(word_wrap)

        # Autosave
        autosave_cfg = self.config.get("autosave", {})
        if isinstance(autosave_cfg, dict):
            autosave_enabled = autosave_cfg.get("enabled", False)
            autosave_interval = autosave_cfg.get("interval", 3000)
        else:
            autosave_enabled = False
            autosave_interval = 3000
        self.autosave_check.setChecked(autosave_enabled)
        self.autosave_interval_spin.setValue(autosave_interval)
        self.autosave_interval_spin.setEnabled(autosave_enabled)

    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme change."""
        self.config.set("theme", theme_name)
        self.config.save()
        self.theme_manager.apply_theme(theme_name)
        logger.info(f"Theme changed to: {theme_name}")

    def _on_font_size_changed(self, size: int) -> None:
        """Handle font size change."""
        font_cfg = self.config.get("font", {})
        if not isinstance(font_cfg, dict):
            font_cfg = {}
        font_cfg["size"] = size
        self.config.set("font", font_cfg)
        self.config.save()
        logger.info(f"Font size changed to: {size}px")

    def _on_tab_size_changed(self, size: int) -> None:
        """Handle tab size change."""
        tabs_cfg = self.config.get("tabs", {})
        if not isinstance(tabs_cfg, dict):
            tabs_cfg = {}
        tabs_cfg["size"] = size
        self.config.set("tabs", tabs_cfg)
        self.config.save()
        logger.info(f"Tab size changed to: {size}")

    def _on_word_wrap_changed(self, enabled: bool) -> None:
        """Handle word wrap toggle."""
        editor_cfg = self.config.get("editor", {})
        if not isinstance(editor_cfg, dict):
            editor_cfg = {}
        editor_cfg["word_wrap"] = enabled
        self.config.set("editor", editor_cfg)
        self.config.save()
        logger.info(f"Word wrap: {'enabled' if enabled else 'disabled'}")

    def _on_autosave_changed(self, enabled: bool) -> None:
        """Handle autosave toggle."""
        autosave_cfg = self.config.get("autosave", {})
        if not isinstance(autosave_cfg, dict):
            autosave_cfg = {}
        autosave_cfg["enabled"] = enabled
        self.config.set("autosave", autosave_cfg)
        self.config.save()
        self.autosave_interval_spin.setEnabled(enabled)
        logger.info(f"Autosave: {'enabled' if enabled else 'disabled'}")

    def _on_autosave_interval_changed(self, interval: int) -> None:
        """Handle autosave interval change."""
        autosave_cfg = self.config.get("autosave", {})
        if not isinstance(autosave_cfg, dict):
            autosave_cfg = {}
        autosave_cfg["interval"] = interval
        self.config.set("autosave", autosave_cfg)
        self.config.save()
        logger.info(f"Autosave interval changed to: {interval}ms")

    def _on_ai_backend_changed(self, backend: str) -> None:
        """Handle AI backend change."""
        ai_cfg = self.config.get("ai", {})
        if not isinstance(ai_cfg, dict):
            ai_cfg = {}
        ai_cfg["provider"] = backend.lower()
        self.config.set("ai", ai_cfg)
        self.config.save()
        logger.info(f"AI backend changed to: {backend}")

    def _on_ai_endpoint_changed(self, endpoint: str) -> None:
        """Handle AI endpoint change."""
        ai_cfg = self.config.get("ai", {})
        if not isinstance(ai_cfg, dict):
            ai_cfg = {}

        if self.ai_backend_combo.currentText().lower() == "ollama":
            ai_cfg["base_url"] = endpoint
        else:
            ai_cfg["api_base"] = endpoint

        self.config.set("ai", ai_cfg)
        self.config.save()
        logger.info(f"AI endpoint changed to: {endpoint}")

    def _on_reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        # This would reload defaults - for now just provide feedback
        logger.info("Reset to defaults requested")
