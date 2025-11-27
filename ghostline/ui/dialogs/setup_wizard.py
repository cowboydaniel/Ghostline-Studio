"""First-run setup wizard for configuring Ghostline Studio AI."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from urllib import request

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtCore import QUrl

from ghostline.core.config import ConfigManager


class SetupWizardDialog(QDialog):
    """Lightweight multi-step wizard for first-time setup."""

    connection_tested = Signal(bool, str)
    ollama_status_changed = Signal(str)

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghostline Studio Setup")
        self.config = config
        self.selected_backend = "none"
        self.selected_model = ""
        self._openai_valid = False
        self._ollama_available = False
        self._ollama_models: list[str] = []

        layout = QVBoxLayout(self)
        self.stack = QStackedLayout()
        layout.addLayout(self.stack)

        self.button_box = QDialogButtonBox(self)
        self.back_button = QPushButton("Back", self)
        self.button_box.addButton(self.back_button, QDialogButtonBox.ActionRole)
        self.next_button = QPushButton("Next", self)
        self.button_box.addButton(self.next_button, QDialogButtonBox.AcceptRole)
        self.cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)

        self.back_button.clicked.connect(self._go_back)
        self.next_button.clicked.connect(self._go_next)
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.button_box)

        self.connection_tested.connect(self._update_openai_status)
        self.ollama_status_changed.connect(self._update_ollama_status)

        self._build_steps()
        self._go_to_step(0)

    # Step construction
    def _build_steps(self) -> None:
        self.stack.addWidget(self._build_welcome())
        self.stack.addWidget(self._build_backend_choice())
        self.stack.addWidget(self._build_summary())

    def _build_welcome(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Welcome to Ghostline Studio", widget)
        title.setObjectName("WizardTitle")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle = QLabel(
            "Ghostline Studio can use AI to understand your codebase and assist with explanations, navigation, and refactors.",
            widget,
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)

        skip = QPushButton("Skip for now", widget)
        skip.clicked.connect(self._skip_ai)
        skip.setAutoDefault(False)
        layout.addWidget(skip, alignment=Qt.AlignRight)
        return widget

    def _build_backend_choice(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(10)

        prompt = QLabel("Choose how Ghostline Studio should access AI capabilities.", widget)
        layout.addWidget(prompt)

        self.backend_group = QButtonGroup(self)
        self.backend_group.buttonToggled.connect(self._backend_changed)

        # OpenAI option
        openai_box = QGroupBox("OpenAI (Cloud)", widget)
        openai_layout = QVBoxLayout(openai_box)
        openai_layout.addWidget(QLabel("Uses your OpenAI API key to access cloud models.", openai_box))

        openai_form = QFormLayout()
        self.openai_key = QLineEdit(openai_box)
        self.openai_key.setPlaceholderText("sk-...")
        self.openai_key.textChanged.connect(lambda _: self._update_next_enabled())
        self.openai_model = QComboBox(openai_box)
        self.openai_model.addItems(["gpt-4o-mini", "gpt-4o", "o3-mini"])
        default_model = self.config.get("ai", {}).get("model")
        if default_model:
            self.openai_model.setCurrentText(default_model)
        self.openai_endpoint = QLineEdit(openai_box)
        self.openai_endpoint.setText(self.config.get("ai", {}).get("openai_endpoint", "https://api.openai.com"))
        openai_form.addRow("API Key", self.openai_key)
        openai_form.addRow("Model", self.openai_model)
        openai_form.addRow("Endpoint", self.openai_endpoint)
        openai_layout.addLayout(openai_form)

        openai_test_row = QHBoxLayout()
        self.test_openai_btn = QPushButton("Test connection", openai_box)
        self.test_openai_btn.clicked.connect(self._test_openai_connection)
        self.openai_status = QLabel("Not tested", openai_box)
        openai_test_row.addWidget(self.test_openai_btn)
        openai_test_row.addWidget(self.openai_status)
        openai_test_row.addStretch(1)
        openai_layout.addLayout(openai_test_row)

        self._openai_radio = QRadioButton("Use OpenAI", openai_box)
        self.backend_group.addButton(self._openai_radio)
        openai_layout.addWidget(self._openai_radio)
        layout.addWidget(openai_box)

        # Ollama option
        ollama_box = QGroupBox("Local Ollama", widget)
        ollama_layout = QVBoxLayout(ollama_box)
        ollama_layout.addWidget(QLabel("Runs AI models locally on your machine.", ollama_box))

        self.ollama_status_label = QLabel("Checking for ollama...", ollama_box)
        self.ollama_model_combo = QComboBox(ollama_box)
        self.ollama_model_combo.currentTextChanged.connect(lambda _: self._update_next_enabled())
        self.pull_model_btn = QPushButton("Pull another model…", ollama_box)
        self.pull_model_btn.clicked.connect(self._prompt_pull_model)

        ollama_buttons = QHBoxLayout()
        self.install_ollama_btn = QPushButton("Install Ollama", ollama_box)
        self.install_ollama_btn.clicked.connect(self._open_ollama_download)
        self.refresh_ollama_btn = QPushButton("Re-check", ollama_box)
        self.refresh_ollama_btn.clicked.connect(self._check_ollama)
        ollama_buttons.addWidget(self.install_ollama_btn)
        ollama_buttons.addWidget(self.refresh_ollama_btn)
        ollama_buttons.addStretch(1)

        self.ollama_logs = QTextEdit(ollama_box)
        self.ollama_logs.setReadOnly(True)
        self.ollama_logs.setPlaceholderText("Model download progress will appear here.")

        self._ollama_radio = QRadioButton("Use Local Ollama", ollama_box)
        self.backend_group.addButton(self._ollama_radio)

        ollama_layout.addWidget(self.ollama_status_label)
        ollama_layout.addWidget(self.ollama_model_combo)
        ollama_layout.addWidget(self.pull_model_btn)
        ollama_layout.addLayout(ollama_buttons)
        ollama_layout.addWidget(self.ollama_logs)
        ollama_layout.addWidget(self._ollama_radio)
        layout.addWidget(ollama_box)

        # None option
        none_box = QGroupBox("No AI", widget)
        none_layout = QVBoxLayout(none_box)
        none_layout.addWidget(QLabel("Run Ghostline Studio without AI for now.", none_box))
        self._none_radio = QRadioButton("Disable AI for now", none_box)
        self.backend_group.addButton(self._none_radio)
        none_layout.addWidget(self._none_radio)
        layout.addWidget(none_box)

        layout.addStretch(1)
        self._none_radio.setChecked(True)
        self._check_ollama()
        return widget

    def _build_summary(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(8)

        self.summary_label = QLabel("Review your AI settings.", widget)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        layout.addStretch(1)
        return widget

    # Navigation
    def _go_to_step(self, step: int) -> None:
        self.stack.setCurrentIndex(step)
        self.back_button.setEnabled(step > 0)
        is_last = step == self.stack.count() - 1
        self.next_button.setText("Finish" if is_last else "Next")
        self._update_next_enabled()
        if is_last:
            self._refresh_summary()

    def _go_back(self) -> None:
        step = max(0, self.stack.currentIndex() - 1)
        self._go_to_step(step)

    def _go_next(self) -> None:
        if self.stack.currentIndex() < self.stack.count() - 1:
            self._go_to_step(self.stack.currentIndex() + 1)
            return
        self._finish()

    # Step actions
    def _skip_ai(self) -> None:
        self.selected_backend = "none"
        self.selected_model = ""
        self._finish()

    def _backend_changed(self, button=None, checked: bool | None = None) -> None:
        # Ignore toggle-off events when receiving the button/checked signature
        if checked is False:
            return
        if self._openai_radio.isChecked():
            self.selected_backend = "openai"
        elif self._ollama_radio.isChecked():
            self.selected_backend = "ollama"
        elif self._none_radio.isChecked():
            self.selected_backend = "none"
        self._update_next_enabled()

    def _update_next_enabled(self) -> None:
        ready = False
        if self.stack.currentIndex() == 0:
            ready = True
        elif self.selected_backend == "openai":
            ready = bool(self.openai_key.text().strip()) or self._openai_valid
        elif self.selected_backend == "ollama":
            ready = self._ollama_available and bool(self.ollama_model_combo.currentText())
        else:
            ready = True
        self.next_button.setEnabled(ready)

    # OpenAI helpers
    def _test_openai_connection(self) -> None:
        api_key = self.openai_key.text().strip()
        endpoint = self.openai_endpoint.text().strip().rstrip("/") or "https://api.openai.com"
        self.openai_status.setText("Testing...")
        self.test_openai_btn.setEnabled(False)

        def worker() -> None:
            try:
                req = request.Request(f"{endpoint}/v1/models")
                if api_key:
                    req.add_header("Authorization", f"Bearer {api_key}")
                with request.urlopen(req, timeout=8) as resp:  # type: ignore[arg-type]
                    payload = json.loads(resp.read().decode("utf-8")) if resp.status < 400 else {}
                if payload.get("data") is not None or payload.get("object"):
                    self.connection_tested.emit(True, "Connection successful")
                else:
                    self.connection_tested.emit(False, "Unexpected response from OpenAI")
            except Exception as exc:  # noqa: BLE001
                self.connection_tested.emit(False, f"Failed to connect: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _update_openai_status(self, ok: bool, message: str) -> None:
        self._openai_valid = ok
        self.openai_status.setText(message)
        color = "green" if ok else "tomato"
        self.openai_status.setStyleSheet(f"color: {color};")
        self.test_openai_btn.setEnabled(True)
        self._update_next_enabled()

    # Ollama helpers
    def _check_ollama(self) -> None:
        available = shutil.which("ollama") is not None
        if not available:
            self._ollama_available = False
            self.ollama_status_changed.emit("Ollama is not installed.")
            self.ollama_model_combo.clear()
            return
        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._ollama_available = True
                self.ollama_status_changed.emit(f"Ollama detected ({result.stdout.strip()})")
                self._refresh_ollama_models()
            else:
                self._ollama_available = False
                self.ollama_status_changed.emit("Unable to communicate with ollama.")
        except FileNotFoundError:
            self._ollama_available = False
            self.ollama_status_changed.emit("Ollama command not found.")
        self._update_next_enabled()

    def _update_ollama_status(self, message: str) -> None:
        self.ollama_status_label.setText(message)

    def _refresh_ollama_models(self) -> None:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())
            models: list[str] = []
            if result.stdout.strip().startswith("["):
                payload = json.loads(result.stdout)
                models = [item.get("name", "") for item in payload if item.get("name")]
            else:
                for line in result.stdout.splitlines():
                    if not line.strip():
                        continue
                    models.append(line.split()[0])
            self._ollama_models = [m for m in models if m]
            self.ollama_model_combo.clear()
            self.ollama_model_combo.addItems(self._ollama_models)
            if not self._ollama_models:
                default_model = self.config.get("ai", {}).get("default_ollama_model", "codellama:7b-code")
                self._pull_model(default_model)
            self._update_next_enabled()
        except Exception as exc:  # noqa: BLE001
            self.ollama_logs.append(f"Unable to list models: {exc}")
            self._ollama_available = False
            self._update_next_enabled()

    def _prompt_pull_model(self) -> None:
        name, ok = QInputDialog.getText(self, "Pull model", "Model name", text="codellama:7b-code")
        if ok and name:
            self._pull_model(name)

    def _pull_model(self, model: str) -> None:
        if not shutil.which("ollama"):
            QMessageBox.warning(self, "Ollama missing", "Install Ollama before pulling models.")
            return
        self.ollama_logs.append(f"Pulling {model}...")
        self.ollama_status_label.setText(f"Downloading {model}…")
        self.ollama_model_combo.setEnabled(False)
        self.pull_model_btn.setEnabled(False)

        process = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def monitor() -> None:
            assert process.stdout
            for line in process.stdout:
                cleaned = line.strip()
                if cleaned:
                    QTimer.singleShot(0, lambda txt=cleaned: self.ollama_logs.append(txt))
            process.wait()
            if process.returncode == 0:
                QTimer.singleShot(0, lambda: self.ollama_logs.append(f"{model} ready."))
                self.ollama_status_changed.emit(f"Ollama ready with {model}.")
                QTimer.singleShot(200, self._refresh_ollama_models)
            else:
                QTimer.singleShot(0, lambda: self.ollama_logs.append(f"Failed to pull {model}."))
            QTimer.singleShot(200, lambda: self.pull_model_btn.setEnabled(True))
            QTimer.singleShot(200, lambda: self.ollama_model_combo.setEnabled(True))

        threading.Thread(target=monitor, daemon=True).start()

    def _open_ollama_download(self) -> None:
        if sys.platform.startswith("linux"):
            self.ollama_logs.append("Installing Ollama for Linux…")
            self.install_ollama_btn.setEnabled(False)
            self.refresh_ollama_btn.setEnabled(False)

            process = subprocess.Popen(
                ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            def monitor_install() -> None:
                assert process.stdout
                for line in process.stdout:
                    cleaned = line.strip()
                    if cleaned:
                        QTimer.singleShot(0, lambda txt=cleaned: self.ollama_logs.append(txt))
                process.wait()
                QTimer.singleShot(0, lambda: self.install_ollama_btn.setEnabled(True))
                QTimer.singleShot(0, lambda: self.refresh_ollama_btn.setEnabled(True))
                QTimer.singleShot(500, self._check_ollama)

            threading.Thread(target=monitor_install, daemon=True).start()
            return

        QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
        QTimer.singleShot(4000, self._check_ollama)

    # Finish
    def _refresh_summary(self) -> None:
        backend = {
            "openai": "OpenAI (Cloud)",
            "ollama": "Local Ollama",
            "none": "No AI",
        }.get(self.selected_backend, self.selected_backend)
        model = ""
        if self.selected_backend == "openai":
            model = self.openai_model.currentText()
        elif self.selected_backend == "ollama":
            model = self.ollama_model_combo.currentText()
        self.summary_label.setText(f"Backend: {backend}\nModel: {model or 'N/A'}")

    def _finish(self) -> None:
        ai_cfg = self.config.settings.setdefault("ai", {})
        ai_cfg["backend"] = self.selected_backend
        ai_cfg["enabled"] = self.selected_backend != "none"
        if self.selected_backend == "openai":
            ai_cfg["api_key"] = self.openai_key.text().strip()
            ai_cfg["model"] = self.openai_model.currentText()
            ai_cfg["openai_endpoint"] = self.openai_endpoint.text().strip() or "https://api.openai.com"
        elif self.selected_backend == "ollama":
            ai_cfg["model"] = self.ollama_model_combo.currentText() or self.config.get("ai", {}).get("default_ollama_model")
            ai_cfg["backend"] = "ollama"
        else:
            ai_cfg["model"] = ""
        self.config.settings["first_run_completed"] = True
        self.config.save()
        self.accept()

    # Utilities for embedding
    def selected_settings(self) -> tuple[str, str]:
        return self.selected_backend, self.openai_model.currentText() if self.selected_backend == "openai" else self.ollama_model_combo.currentText()

