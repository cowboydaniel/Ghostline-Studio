"""UI panel for controlling the debugger."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.debugger.debugger_manager import DebuggerManager


class DebuggerPanel(QWidget):
    def __init__(self, manager: DebuggerManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._current_file_provider = None

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.variables = QListWidget(self)
        self.stack = QListWidget(self)

        self.config_combo = QComboBox(self)
        self.config_combo.setEditable(False)
        self.config_combo.setPlaceholderText("ghostline_launch.json")

        self.button_run = QPushButton("Start", self)
        self.button_continue = QPushButton("Continue", self)
        self.button_step = QPushButton("Step Over", self)
        self.button_restart = QPushButton("Restart", self)
        self.button_stop = QPushButton("Stop", self)
        for button in (self.button_run, self.button_continue, self.button_step, self.button_restart, self.button_stop):
            button.setEnabled(False)

        self.button_run.clicked.connect(self._run_active_config)
        self.button_continue.clicked.connect(self.manager.continue_execution)
        self.button_step.clicked.connect(self.manager.step)
        self.button_restart.clicked.connect(self.manager.restart)
        self.button_stop.clicked.connect(self.manager.stop)

        layout = QVBoxLayout(self)
        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Configuration:", self))
        config_row.addWidget(self.config_combo, stretch=1)
        choose_btn = QPushButton("Select File", self)
        choose_btn.clicked.connect(self._choose_and_run)
        config_row.addWidget(choose_btn)
        layout.addLayout(config_row)

        buttons = QHBoxLayout()
        buttons.addWidget(self.button_run)
        buttons.addWidget(self.button_continue)
        buttons.addWidget(self.button_step)
        buttons.addWidget(self.button_restart)
        buttons.addWidget(self.button_stop)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Call Stack"))
        layout.addWidget(self.stack)
        layout.addWidget(QLabel("Variables"))
        layout.addWidget(self.variables)
        layout.addWidget(QLabel("Console"))
        layout.addWidget(self.console)

        self.manager.output.connect(self._append_output)
        self.manager.state_changed.connect(self._show_state)

    def set_configured(self, available: bool) -> None:
        self.button_run.setEnabled(available)
        self.button_continue.setEnabled(available)
        self.button_step.setEnabled(available)
        self.button_restart.setEnabled(available)
        self.button_stop.setEnabled(available)
        hint = "Select a debug configuration to enable controls." if not available else "Ready to debug"
        self.console.setPlaceholderText(hint)

    def _append_output(self, text: str) -> None:
        self.console.append(text)

    def _show_state(self, state: str) -> None:
        self.console.append(f"State: {state}")

    def set_current_file_provider(self, provider) -> None:
        self._current_file_provider = provider

    def refresh_configurations(self, configs: list[str]) -> None:
        self.config_combo.clear()
        self.config_combo.addItems(configs)
        if not configs:
            self.config_combo.setPlaceholderText("Add a launch configuration")
        else:
            self.config_combo.setCurrentIndex(0)

    def _choose_and_run(self) -> None:
        script, _ = QFileDialog.getOpenFileName(self, "Select Python file", filter="Python Files (*.py)")
        if script:
            self.manager.launch(script)

    def _run_active_config(self) -> None:
        if self._current_file_provider:
            current_file = self._current_file_provider()
        else:
            current_file = None
        config_name = self.config_combo.currentText() if self.config_combo.currentText() else None
        if current_file:
            self.manager.launch_for_file(current_file, config_name)
        else:
            self.manager.output.emit("No active file selected for debugging.")
