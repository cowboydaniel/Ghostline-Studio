"""Bootstrap script to install dependencies and launch Ghostline Studio."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Set, Tuple

# Map imported module names to the pip packages that provide them.
DEPENDENCY_PACKAGE_MAP: dict[str, str] = {
    "PySide6": "PySide6",
    "shiboken6": "shiboken6",
    "yaml": "PyYAML",
    "httpx": "httpx",
    "openai": "openai",
    "pytest": "pytest",
}

# Modules that should always be installed even if they are not discovered in the AST scan
# (for example, shiboken6 ships with PySide6 but is listed explicitly for clarity).
ESSENTIAL_MODULES: set[str] = {
    "PySide6",
    "shiboken6",
    "yaml",
    "httpx",
    "openai",
}

PROJECT_ROOT = Path(__file__).resolve().parent


def _collect_imports(root: Path) -> Set[str]:
    """Return the set of top-level import names used in Python files under ``root``."""

    project_modules = {path.stem for path in root.rglob("*.py")}
    stdlib = set(sys.stdlib_module_names)
    discovered: set[str] = set()

    for py_file in root.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8", errors="ignore") as handle:
            try:
                tree = ast.parse(handle.read(), filename=str(py_file))
            except SyntaxError:
                continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.names[0].name if isinstance(node, ast.Import) else node.module
                if not module:
                    continue
                discovered.add(module.split(".")[0])

    external: set[str] = set()
    for name in discovered:
        if name in stdlib or name in project_modules or name == "ghostline":
            continue
        if (root / name).is_dir():
            continue
        external.add(name)

    return external


def _resolve_packages(modules: Iterable[str]) -> Set[Tuple[str, str]]:
    """Map module names to the pip packages that should be installed."""

    resolved: set[tuple[str, str]] = set()
    for module in modules:
        package = DEPENDENCY_PACKAGE_MAP.get(module, module)
        resolved.add((module, package))
    return resolved


def install_dependencies() -> None:
    """Install all external dependencies detected in the repository."""

    imported_modules = _collect_imports(PROJECT_ROOT)
    imported_modules.update(ESSENTIAL_MODULES)

    dependencies = _resolve_packages(imported_modules)
    base_cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages"]

    for module, package in sorted(dependencies, key=lambda item: item[1].lower()):
        if importlib.util.find_spec(module) is not None:
            continue
        subprocess.check_call(base_cmd + [package])


def main() -> None:
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    install_dependencies()

    from ghostline.main import main as run_main

    raise SystemExit(run_main())


if __name__ == "__main__":
    main()
