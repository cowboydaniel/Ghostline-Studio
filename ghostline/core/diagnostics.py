"""Diagnostics collection and export for Ghostline Studio."""
from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ghostline.core.config import CONFIG_DIR, LOG_DIR, LOG_FILE, USER_SETTINGS_PATH
from ghostline.core.urls import get_app_version

logger = logging.getLogger(__name__)


class DiagnosticsCollector:
    """Collects diagnostics information from the system and application."""

    SENSITIVE_PATTERNS = [
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "password",
        "token",
        "auth",
        "credential",
    ]

    def __init__(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ghostline_diag_"))

    def collect_all(self) -> dict[str, Any]:
        """Collect all diagnostics information."""
        return {
            "system_info": self._collect_system_info(),
            "app_info": self._collect_app_info(),
            "config": self._collect_config(),
            "logs": self._collect_logs(),
        }

    def _collect_system_info(self) -> dict[str, str]:
        """Collect system information."""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "architecture": platform.machine(),
        }

    def _collect_app_info(self) -> dict[str, str]:
        """Collect application information."""
        app_version = get_app_version()

        return {
            "app_version": app_version,
            "config_dir": str(CONFIG_DIR),
            "log_dir": str(LOG_DIR if LOG_DIR.exists() else LOG_FILE.parent),
        }

    def _collect_config(self) -> dict[str, Any]:
        """Collect sanitized configuration."""
        config_data = {}

        # Read settings files
        config_files = [USER_SETTINGS_PATH]
        for extra_cfg in CONFIG_DIR.glob("*.yaml"):
            if extra_cfg not in config_files:
                config_files.append(extra_cfg)
        for extra_cfg in CONFIG_DIR.glob("*.json"):
            if extra_cfg not in config_files:
                config_files.append(extra_cfg)

        for cfg_file in config_files:
            if cfg_file.exists():
                try:
                    with cfg_file.open("r", encoding="utf-8") as f:
                        content = f.read()
                        # Try to parse as YAML/JSON
                        try:
                            import yaml
                            data = yaml.safe_load(content)
                        except Exception:
                            try:
                                data = json.loads(content)
                            except Exception:
                                data = {"_error": "Could not parse file"}

                        # Redact sensitive data
                        redacted = self._redact_sensitive_data(data)
                        config_data[cfg_file.name] = redacted
                except Exception as e:
                    logger.warning(f"Could not read {cfg_file}: {e}")

        return config_data

    def _collect_logs(self) -> dict[str, str]:
        """Collect log file information."""
        logs = {}

        log_dir = LOG_DIR if LOG_DIR.exists() else LOG_FILE.parent
        if log_dir.exists():
            for log_file in log_dir.glob("ghostline.log*"):
                if log_file.is_file():
                    try:
                        # Get last 100 lines of log
                        with log_file.open("r", encoding="utf-8") as f:
                            lines = f.readlines()
                            last_lines = "".join(lines[-100:])
                            logs[log_file.name] = last_lines
                    except Exception as e:
                        logs[log_file.name] = f"Error reading: {e}"

        if not logs:
            logs["status"] = "No log files found"

        return logs

    def _redact_sensitive_data(self, data: Any, depth: int = 0) -> Any:
        """Recursively redact sensitive data from config."""
        if depth > 10:  # Prevent infinite recursion
            return data

        if isinstance(data, dict):
            redacted = {}
            for key, value in data.items():
                if self._is_sensitive_key(key):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact_sensitive_data(value, depth + 1)
            return redacted
        elif isinstance(data, list):
            return [self._redact_sensitive_data(item, depth + 1) for item in data]
        elif isinstance(data, str):
            # Redact email addresses
            if "@" in data and "." in data:
                return "[REDACTED_EMAIL]"
            return data
        else:
            return data

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key looks sensitive."""
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in self.SENSITIVE_PATTERNS)

    def create_diagnostics_zip(self, output_path: str) -> bool:
        """Create a zip file with all diagnostics.

        Args:
            output_path: Path where to save the zip file

        Returns:
            True if successful
        """
        try:
            # Collect all diagnostics
            all_data = self.collect_all()

            # Write to temp files
            diag_file = self.temp_dir / "diagnostics.json"
            with diag_file.open("w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2)

            # Create the zip file
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in self.temp_dir.iterdir():
                    if item.is_file():
                        archive.write(item, item.name)

            logger.info(f"Diagnostics exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating diagnostics zip: {e}")
            return False
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Could not clean up temp directory: {e}")
