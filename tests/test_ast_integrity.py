from __future__ import annotations

import ast
from pathlib import Path


def _python_files() -> list[Path]:
    project_root = Path(__file__).resolve().parent.parent
    return [path for path in (project_root / "ghostline").rglob("*.py")]


def test_all_python_files_are_parseable() -> None:
    failures: list[tuple[Path, Exception]] = []
    for path in _python_files():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - collect all parse errors
            failures.append((path, exc))
    assert not failures, f"Files failed to parse: {failures}"
