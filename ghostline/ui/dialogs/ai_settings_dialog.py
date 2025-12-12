"""AI configuration panel for Ghostline Studio."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.core.config import ConfigManager
from ghostline.ai.model_registry import ModelDescriptor, ModelRegistry


class AISettingsDialog(QDialog):
    """Expose AI backend configuration and helper tools."""

    openai_models_ready = Signal(list)
    openai_status_ready = Signal(bool, str)

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.registry = ModelRegistry(config)
        self.setWindowTitle("AI Settings")
        self._openai_models: list[ModelDescriptor] = self.registry.openai_models()
        self._model_checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget(self)
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        content_layout = QVBoxLayout(content_widget)

        self.backend_combo = QComboBox(content_widget)
        self.backend_combo.addItems(["openai", "ollama", "claude", "none"])
        self.backend_combo.setCurrentText(self.config.get("ai", {}).get("backend", "none"))
        self.backend_combo.currentTextChanged.connect(self._update_enabled_state)

        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel("Backend"))
        backend_row.addWidget(self.backend_combo)
        backend_row.addStretch(1)
        content_layout.addLayout(backend_row)

        # OpenAI section
        self.openai_group = QGroupBox("OpenAI (Cloud)", content_widget)
        openai_form = QFormLayout(self.openai_group)
        self.openai_key = QLineEdit(self.openai_group)
        self.openai_key.setText(self.registry._openai_settings().get("api_key", ""))
        self.openai_model = QComboBox(self.openai_group)
        self._populate_openai_model_combo()
        self.openai_endpoint = QLineEdit(self.openai_group)
        self.openai_endpoint.setText(self.registry._openai_settings().get("base_url", "https://api.openai.com"))
        self.openai_status = QLabel("", self.openai_group)
        self.test_openai_btn = QPushButton("Test connection", self.openai_group)
        self.test_openai_btn.clicked.connect(self._test_openai)

        openai_form.addRow("API Key", self.openai_key)
        openai_form.addRow("Model", self.openai_model)
        openai_form.addRow("Endpoint", self.openai_endpoint)
        openai_form.addRow(self.test_openai_btn, self.openai_status)

        self.openai_models_box = QGroupBox("OpenAI coding models", self.openai_group)
        self.models_layout = QVBoxLayout(self.openai_models_box)
        helper = QLabel(
            "Only enabled models appear in the AI dock selector. OpenAI models require a valid API key.",
            self.openai_models_box,
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: palette(dark);")
        self.models_layout.addWidget(helper)
        self.model_rows_layout = QVBoxLayout()
        self.models_layout.addLayout(self.model_rows_layout)
        self._rebuild_model_rows()

        openai_form.addRow(self.openai_models_box)

        # Claude (Anthropic) section
        self.claude_group = QGroupBox("Claude (Anthropic)", content_widget)
        claude_form = QFormLayout(self.claude_group)
        self.claude_key = QLineEdit(self.claude_group)
        self.claude_key.setText(self.registry._claude_settings().get("api_key", ""))
        self.claude_model = QComboBox(self.claude_group)
        self._populate_claude_model_combo()
        self.claude_status = QLabel("", self.claude_group)
        self.test_claude_btn = QPushButton("Test connection", self.claude_group)
        self.test_claude_btn.clicked.connect(self._test_claude)

        claude_form.addRow("API Key", self.claude_key)
        claude_form.addRow("Model", self.claude_model)
        claude_form.addRow(self.test_claude_btn, self.claude_status)

        self.claude_models_box = QGroupBox("Claude models", self.claude_group)
        self.claude_models_layout = QVBoxLayout(self.claude_models_box)
        claude_helper = QLabel(
            "Only enabled models appear in the AI dock selector. Claude models require a valid API key.",
            self.claude_models_box,
        )
        claude_helper.setWordWrap(True)
        claude_helper.setStyleSheet("color: palette(dark);")
        self.claude_models_layout.addWidget(claude_helper)
        self.claude_model_rows_layout = QVBoxLayout()
        self.claude_models_layout.addLayout(self.claude_model_rows_layout)
        self._rebuild_claude_model_rows()

        claude_form.addRow(self.claude_models_box)

        # Ollama section
        self.ollama_group = QGroupBox("Local Ollama", content_widget)
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

        content_layout.addWidget(self.openai_group)
        content_layout.addWidget(self.claude_group)
        content_layout.addWidget(self.ollama_group)
        content_layout.addStretch(1)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        buttons_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons_box.accepted.connect(self._save)
        buttons_box.rejected.connect(self.reject)
        layout.addWidget(buttons_box)

        self._check_ollama()
        self._maybe_load_openai_models()
        self._update_enabled_state()

        self.openai_models_ready.connect(
            self._update_openai_models, Qt.ConnectionType.QueuedConnection
        )
        self.openai_status_ready.connect(
            self._update_openai_status, Qt.ConnectionType.QueuedConnection
        )

    def _update_enabled_state(self) -> None:
        backend = self.backend_combo.currentText()
        self.openai_group.setEnabled(backend == "openai")
        self.claude_group.setEnabled(backend == "claude")
        self.ollama_group.setEnabled(backend == "ollama")

    # OpenAI helpers
    def _test_openai(self) -> None:
        self._load_openai_models(force_status=True)

    def _maybe_load_openai_models(self) -> None:
        if self.openai_key.text().strip():
            self._load_openai_models()

    def _populate_openai_model_combo(self) -> None:
        current_model = self.registry.last_used_model()
        current_id = None
        if current_model and current_model.provider == "openai":
            current_id = current_model.id
        if not current_id:
            current_id = self.config.get("ai", {}).get("model")
        if not current_id and self._openai_models:
            enabled = [model.id for model in self._openai_models if model.enabled]
            current_id = enabled[0] if enabled else self._openai_models[0].id

        self.openai_model.clear()
        for model in self._openai_models:
            self.openai_model.addItem(model.label, userData=model.id)

        if current_id:
            index = self.openai_model.findData(current_id)
            if index != -1:
                self.openai_model.setCurrentIndex(index)
        elif self._openai_models:
            self.openai_model.setCurrentIndex(0)

    def _refresh_checkbox_states(self) -> None:
        for model in self._openai_models:
            checkbox = self._model_checkboxes.get(model.id)
            if checkbox:
                checkbox.setChecked(model.enabled)

    def _rebuild_model_rows(self) -> None:
        while self.model_rows_layout.count():
            item = self.model_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
        self._model_checkboxes.clear()
        for descriptor in self._openai_models:
            row = QHBoxLayout()
            checkbox = QCheckBox(descriptor.label, self.openai_models_box)
            checkbox.setChecked(descriptor.enabled)
            checkbox.stateChanged.connect(lambda _state, m=descriptor: self._toggle_model(m))
            self._model_checkboxes[descriptor.id] = checkbox
            row.addWidget(checkbox)
            badge = QLabel(descriptor.provider.capitalize(), self.openai_models_box)
            badge.setStyleSheet(
                "padding: 2px 6px; border-radius: 8px; background: palette(midlight); font-size: 11px;"
            )
            row.addWidget(badge)
            if descriptor.kind:
                kind_badge = QLabel(descriptor.kind.title(), self.openai_models_box)
                kind_badge.setStyleSheet(
                    "padding: 2px 6px; border-radius: 8px; background: palette(mid); font-size: 11px;"
                )
                row.addWidget(kind_badge)
            desc_label = QLabel(descriptor.description or "", self.openai_models_box)
            desc_label.setStyleSheet("color: palette(dark);")
            row.addWidget(desc_label, 1)
            self.model_rows_layout.addLayout(row)

    def _toggle_model(self, model: ModelDescriptor) -> None:
        checkbox = self._model_checkboxes.get(model.id)
        if checkbox:
            model.enabled = checkbox.isChecked()
        enabled_ids = [
            descriptor.id
            for descriptor in self._openai_models
            if self._model_checkboxes.get(descriptor.id) and self._model_checkboxes[descriptor.id].isChecked()
        ]
        for descriptor in self._openai_models:
            descriptor.enabled = descriptor.id in enabled_ids
        self.registry.set_enabled_openai_models(enabled_ids)

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
                    self.openai_models_ready.emit(models)
                self.openai_status_ready.emit(ok, message)

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
        descriptors = [ModelDescriptor(model_id, model_id, "openai", "code", model_id in models) for model_id in models]
        self._openai_models = descriptors
        self.registry._openai_settings()["available_models"] = [m.to_dict() for m in descriptors]
        self.registry.set_enabled_openai_models([m.id for m in descriptors])
        self._rebuild_model_rows()
        self._populate_openai_model_combo()
        self._refresh_checkbox_states()
        self.openai_model.setEnabled(True)

    def _update_openai_status(self, ok: bool, message: str) -> None:
        self.openai_status.setText(message)
        self.openai_status.setStyleSheet(f"color: {'green' if ok else 'tomato'}")
        self.test_openai_btn.setEnabled(True)
        self.openai_model.setEnabled(True)

    # Claude helpers
    def _test_claude(self) -> None:
        """Test the Claude API connection."""
        api_key = self.claude_key.text().strip()
        if not api_key:
            self.claude_status.setText("Enter an API key first.")
            self.claude_status.setStyleSheet("color: tomato")
            return

        self.claude_status.setText("Testing connection...")
        self.test_claude_btn.setEnabled(False)

        def worker() -> None:
            try:
                import json
                import urllib.request

                url = "https://api.anthropic.com/v1/messages"
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hello"}],
                }
                data = json.dumps(payload).encode("utf-8")
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                }
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        QTimer.singleShot(0, lambda: self._update_claude_status(True, "Connection successful"))
                    else:
                        QTimer.singleShot(0, lambda: self._update_claude_status(False, f"HTTP {resp.status}"))
            except Exception as exc:
                QTimer.singleShot(0, lambda: self._update_claude_status(False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _update_claude_status(self, ok: bool, message: str) -> None:
        """Update the Claude connection status label."""
        self.claude_status.setText(message)
        self.claude_status.setStyleSheet(f"color: {'green' if ok else 'tomato'}")
        self.test_claude_btn.setEnabled(True)

    def _populate_claude_model_combo(self) -> None:
        """Populate the Claude model dropdown."""
        claude_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]

        current_model = self.registry.last_used_model()
        current_id = None
        if current_model and current_model.provider == "claude":
            current_id = current_model.id
        if not current_id:
            claude_cfg = self.registry._claude_settings()
            current_id = claude_cfg.get("default_model", claude_models[0])

        self.claude_model.clear()
        for model_id in claude_models:
            self.claude_model.addItem(model_id, userData=model_id)

        if current_id:
            index = self.claude_model.findData(current_id)
            if index != -1:
                self.claude_model.setCurrentIndex(index)
            else:
                self.claude_model.setCurrentIndex(0)
        else:
            self.claude_model.setCurrentIndex(0)

    def _rebuild_claude_model_rows(self) -> None:
        """Build the checkboxes for Claude models."""
        claude_models = [
            ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "Fast, versatile model for most tasks"),
            ("claude-3-opus-20240229", "Claude 3 Opus", "Most capable model for complex tasks"),
            ("claude-3-haiku-20240307", "Claude 3 Haiku", "Fastest model for simple tasks"),
        ]

        # Clear existing rows
        while self.claude_model_rows_layout.count():
            item = self.claude_model_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get enabled models from settings
        claude_cfg = self.registry._claude_settings()
        enabled_models = claude_cfg.get("enabled_models", [claude_models[0][0]])

        if not hasattr(self, "_claude_model_checkboxes"):
            self._claude_model_checkboxes: dict[str, QCheckBox] = {}
        self._claude_model_checkboxes.clear()

        for model_id, label, description in claude_models:
            row = QHBoxLayout()
            checkbox = QCheckBox(label, self.claude_models_box)
            checkbox.setChecked(model_id in enabled_models)
            checkbox.stateChanged.connect(lambda _state, m=model_id: self._toggle_claude_model(m))
            self._claude_model_checkboxes[model_id] = checkbox
            row.addWidget(checkbox)

            badge = QLabel("Claude", self.claude_models_box)
            badge.setStyleSheet(
                "padding: 2px 6px; border-radius: 8px; background: palette(midlight); font-size: 11px;"
            )
            row.addWidget(badge)

            desc_label = QLabel(description, self.claude_models_box)
            desc_label.setStyleSheet("color: palette(dark);")
            row.addWidget(desc_label, 1)
            self.claude_model_rows_layout.addLayout(row)

    def _toggle_claude_model(self, model_id: str) -> None:
        """Toggle a Claude model's enabled state."""
        checkbox = self._claude_model_checkboxes.get(model_id)
        if not checkbox:
            return

        enabled_ids = [
            mid for mid, cb in self._claude_model_checkboxes.items() if cb.isChecked()
        ]

        # Save to config
        claude_cfg = self.registry._claude_settings()
        claude_cfg["enabled_models"] = enabled_ids

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
        providers = ai_cfg.setdefault("providers", {})

        # Save OpenAI settings
        openai_cfg = providers.setdefault("openai", {})
        enabled_ids = [mid for mid, cb in self._model_checkboxes.items() if cb.isChecked()]
        openai_cfg["api_key"] = self.openai_key.text().strip()
        openai_cfg["base_url"] = self._normalized_openai_endpoint()
        openai_cfg["available_models"] = [model.to_dict() for model in self._openai_models]
        openai_cfg["enabled_models"] = enabled_ids
        ai_cfg["openai_endpoint"] = openai_cfg["base_url"]
        ai_cfg["api_key"] = openai_cfg["api_key"]

        # Save Claude settings
        claude_cfg = providers.setdefault("claude", {})
        claude_enabled_ids = [mid for mid, cb in self._claude_model_checkboxes.items() if cb.isChecked()]
        claude_cfg["api_key"] = self.claude_key.text().strip()
        claude_cfg["enabled_models"] = claude_enabled_ids
        selected_claude = self.claude_model.currentData() or self.claude_model.currentText()
        claude_cfg["default_model"] = selected_claude

        selected_openai = self.openai_model.currentData() or self.openai_model.currentText()
        selected_ollama = self.ollama_models.currentText()

        if backend == "claude":
            ai_cfg["model"] = selected_claude
        elif backend == "openai":
            ai_cfg["model"] = selected_openai
        else:
            ai_cfg["model"] = selected_ollama

        if selected_openai and backend == "openai":
            ai_cfg["last_used_model"] = ModelDescriptor(
                selected_openai, self.openai_model.currentText(), "openai", "code", True
            ).to_dict()
        elif selected_claude and backend == "claude":
            ai_cfg["last_used_model"] = ModelDescriptor(
                selected_claude, selected_claude, "claude", "code", True
            ).to_dict()
        elif selected_ollama and backend == "ollama":
            ai_cfg["last_used_model"] = ModelDescriptor(
                selected_ollama, selected_ollama, "ollama", "code", True
            ).to_dict()
        self.config.save()
        self.accept()

