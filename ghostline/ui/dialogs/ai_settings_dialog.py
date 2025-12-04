"""AI configuration panel for Ghostline Studio."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ghostline.core.config import ConfigManager


class AISettingsDialog(QDialog):
    """Expose AI backend configuration and helper tools."""

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("AI Settings")

        layout = QVBoxLayout(self)
        self.backend_combo = QComboBox(self)
        self.backend_combo.addItems(["openai", "ollama", "none"])
        self.backend_combo.setCurrentText(self.config.get("ai", {}).get("backend", "none"))
        self.backend_combo.currentTextChanged.connect(self._update_enabled_state)

        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel("Backend"))
        backend_row.addWidget(self.backend_combo)
        backend_row.addStretch(1)
        layout.addLayout(backend_row)

        # OpenAI section
        self.openai_group = QGroupBox("OpenAI (Cloud)", self)
        openai_form = QFormLayout(self.openai_group)
        self.openai_key = QLineEdit(self.openai_group)
        self.openai_key.setText(self.config.get("ai", {}).get("api_key", ""))
        self.openai_model = QComboBox(self.openai_group)
        saved_model = self.config.get("ai", {}).get("model", "gpt-4o-mini")
        self.openai_model.addItem(saved_model)
        self.openai_model.setCurrentText(saved_model)
        self.openai_endpoint = QLineEdit(self.openai_group)
        self.openai_endpoint.setText(self.config.get("ai", {}).get("openai_endpoint", "https://api.openai.com"))
        self.openai_status = QLabel("", self.openai_group)
        self.test_openai_btn = QPushButton("Test connection", self.openai_group)
        self.test_openai_btn.clicked.connect(self._test_openai)

        openai_form.addRow("API Key", self.openai_key)
        openai_form.addRow("Model", self.openai_model)
        openai_form.addRow("Endpoint", self.openai_endpoint)
        openai_form.addRow(self.test_openai_btn, self.openai_status)

        # Ollama section
        self.ollama_group = QGroupBox("Local Ollama", self)
        ollama_layout = QVBoxLayout(self.ollama_group)
        self.ollama_status = QLabel("Checking for ollama...", self.ollama_group)
        self.ollama_models = QComboBox(self.ollama_group)
        self.pull_button = QPushButton("Pull model", self.ollama_group)
        self.pull_button.clicked.connect(self._pull_model)
        self.refresh_button = QPushButton("Refresh models", self.ollama_group)
        self.refresh_button.clicked.connect(self._refresh_ollama_models)
        buttons = QHBoxLayout()
        buttons.addWidget(self.pull_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)
        self.ollama_logs = QTextEdit(self.ollama_group)
        self.ollama_logs.setReadOnly(True)
        self.ollama_logs.setPlaceholderText("Model pulls and list updates will appear here.")

        ollama_layout.addWidget(self.ollama_status)
        ollama_layout.addWidget(self.ollama_models)
        ollama_layout.addLayout(buttons)
        ollama_layout.addWidget(self.ollama_logs)

        layout.addWidget(self.openai_group)
        layout.addWidget(self.ollama_group)
        layout.addStretch(1)

        buttons_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons_box.accepted.connect(self._save)
        buttons_box.rejected.connect(self.reject)
        layout.addWidget(buttons_box)

        self._check_ollama()
        self._maybe_load_openai_models()
        self._update_enabled_state()

    def _update_enabled_state(self) -> None:
        backend = self.backend_combo.currentText()
        self.openai_group.setEnabled(backend == "openai")
        self.ollama_group.setEnabled(backend == "ollama")

    # OpenAI helpers
    def _test_openai(self) -> None:
        self._load_openai_models(force_status=True)

    def _maybe_load_openai_models(self) -> None:
        if self.openai_key.text().strip():
            self._load_openai_models()

    def _normalized_openai_endpoint(self) -> str:
        return self.openai_endpoint.text().strip().rstrip("/") or "https://api.openai.com"

    def _load_openai_models(self, force_status: bool = False) -> None:
        api_key = self.openai_key.text().strip()
        if not api_key:
            if force_status:
                self._update_openai_status(False, "Enter an API key first.")
            return

        endpoint = self._normalized_openai_endpoint()
        base_url = f"{endpoint}/v1" if not endpoint.endswith("/v1") else endpoint
        self.openai_status.setText("Fetching models...")
        self.test_openai_btn.setEnabled(False)
        self.openai_model.setEnabled(False)

        def worker() -> None:
            timeout_seconds = 8

            def finish(ok: bool, message: str, models: list[str] | None = None) -> None:
                if models is not None:
                    QTimer.singleShot(0, lambda: self._update_openai_models(models))
                QTimer.singleShot(0, lambda: self._update_openai_status(ok, message))

            try:
                try:
                    import httpx
                    from openai import APITimeoutError, OpenAI
                except ImportError:
                    finish(
                        False, "OpenAI client not installed. Install with 'pip install openai'."
                    )
                    return

                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    http_client=httpx.Client(timeout=timeout_seconds),
                )
                response = client.models.list()
                models = []
                for model in response.data:
                    model_id = getattr(model, "id", "")
                    if not model_id:
                        continue
                    capabilities = getattr(model, "capabilities", None)
                    supports_chat = bool(getattr(capabilities, "chat_completions", False)) if capabilities else False
                    if supports_chat or model_id.startswith(("gpt-", "o1", "o3")):
                        models.append(model_id)
                models = sorted(models, reverse=False)
                if not models:
                    raise RuntimeError("No models returned")
                finish(True, "Connection successful", models)
            except (APITimeoutError, httpx.TimeoutException):
                finish(False, f"Request timed out after {timeout_seconds}s")
            except Exception as exc:  # noqa: BLE001
                finish(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _update_openai_models(self, models: list[str]) -> None:
        current = self.config.get("ai", {}).get("model") or self.openai_model.currentText()
        self.openai_model.clear()
        self.openai_model.addItems(models)
        if current and current in models:
            self.openai_model.setCurrentText(current)
        elif models:
            self.openai_model.setCurrentText(models[0])
        self.openai_model.setEnabled(True)

    def _update_openai_status(self, ok: bool, message: str) -> None:
        self.openai_status.setText(message)
        self.openai_status.setStyleSheet(f"color: {'green' if ok else 'tomato'}")
        self.test_openai_btn.setEnabled(True)
        self.openai_model.setEnabled(True)

    # Ollama helpers
    def _check_ollama(self) -> None:
        available = shutil.which("ollama") is not None
        if not available:
            self.ollama_status.setText("Ollama not installed.")
            self.ollama_models.clear()
            return
        try:
            version = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
            if version.returncode == 0:
                self.ollama_status.setText(f"Ollama detected ({version.stdout.strip()})")
                self._refresh_ollama_models()
            else:
                self.ollama_status.setText("Unable to talk to ollama")
        except FileNotFoundError:
            self.ollama_status.setText("Ollama not installed.")

    def _refresh_ollama_models(self) -> None:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=8)
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
            self.ollama_models.clear()
            self.ollama_models.addItems(models)
            if models:
                default_model = self.config.get("ai", {}).get("model", models[0])
                self.ollama_models.setCurrentText(default_model)
        except Exception as exc:  # noqa: BLE001
            self.ollama_logs.append(f"Unable to list models: {exc}")

    def _pull_model(self) -> None:
        model = self.ollama_models.currentText() or self.config.get("ai", {}).get("default_ollama_model", "codellama:7b-code")
        if not shutil.which("ollama"):
            QMessageBox.warning(self, "Ollama missing", "Install Ollama to pull models.")
            return
        self.ollama_logs.append(f"Pulling {model}...")
        process = subprocess.Popen(["ollama", "pull", model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        def monitor() -> None:
            assert process.stdout
            for line in process.stdout:
                cleaned = line.strip()
                if cleaned:
                    QTimer.singleShot(0, lambda txt=cleaned: self.ollama_logs.append(txt))
            process.wait()
            if process.returncode == 0:
                QTimer.singleShot(0, lambda: self.ollama_logs.append(f"{model} ready."))
                QTimer.singleShot(200, self._refresh_ollama_models)
            else:
                QTimer.singleShot(0, lambda: self.ollama_logs.append("Pull failed."))

        threading.Thread(target=monitor, daemon=True).start()

    def _save(self) -> None:
        backend = self.backend_combo.currentText()
        ai_cfg = self.config.settings.setdefault("ai", {})
        ai_cfg["backend"] = backend
        ai_cfg["enabled"] = backend != "none"
        ai_cfg["api_key"] = self.openai_key.text().strip()
        ai_cfg["model"] = (
            self.openai_model.currentText() if backend == "openai" else self.ollama_models.currentText()
        )
        ai_cfg["openai_endpoint"] = self.openai_endpoint.text().strip() or "https://api.openai.com"
        self.config.save()
        self.accept()

