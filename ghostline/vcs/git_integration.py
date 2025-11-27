"""Lightweight git helpers."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitIntegration:
    def branch_name(self, path: str | None) -> Optional[str]:
        if not path:
            return None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=Path(path),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def is_dirty(self, path: str | None) -> bool:
        if not path:
            return False
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=Path(path),
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
