"""Dependency installation module with progress reporting."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Callable, Iterable, Set


def project_root() -> Path:
    """Return the absolute path to the repository root."""
    return Path(__file__).resolve().parent.parent.parent


def is_stdlib_module(name: str) -> bool:
    """Return True if ``name`` resolves to a standard library module."""
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        return False
    if spec is None:
        return False

    if spec.origin in (None, "built-in", "frozen"):
        return True

    stdlib_path = Path(sysconfig.get_paths()["stdlib"]).resolve()
    try:
        origin = Path(spec.origin).resolve()
    except OSError:
        return True
    return origin == stdlib_path or stdlib_path in origin.parents


def is_first_party_module(name: str, project_root: Path) -> bool:
    """Return True if the module comes from inside ``project_root``."""
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        return False
    if spec is None or spec.origin is None:
        return False
    try:
        origin = Path(spec.origin).resolve()
    except OSError:
        return False
    try:
        root = project_root.resolve()
    except OSError:
        root = project_root
    return root in origin.parents or origin == root


NEVER_PIP_INSTALL = {
    "os",
    "sys",
    "math",
    "time",
    "builtins",
    "_ast",
    "types",
    "tests",
    "test",
}

IMPORT_TO_PIP_PACKAGE = {
    "yaml": "PyYAML",
    "PIL": "Pillow",
}


def _first_party_packages(root: Path) -> Set[str]:
    """Detect top-level first-party package names under ``root``."""
    packages: set[str] = set()
    for entry in root.iterdir():
        if entry.is_dir() and (entry / "__init__.py").exists():
            packages.add(entry.name)
    packages.add("ghostline")
    return packages


def _discover_imports(py_file: Path) -> Set[str]:
    """Parse a Python file and return discovered top-level import names."""
    discovered: set[str] = set()
    try:
        source = py_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return discovered

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return discovered

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name:
                    discovered.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            module = node.module
            if module:
                name = module.split(".")[0]
                if name:
                    discovered.add(name)
    return discovered


def collect_dependencies(root: Path) -> Set[str]:
    """Collect third-party dependencies used in the project."""
    first_party = _first_party_packages(root)
    discovered: set[str] = set()

    for py_file in root.rglob("*.py"):
        discovered.update(_discover_imports(py_file))

    dependencies: set[str] = set()
    for name in discovered:
        if not name or name in first_party:
            continue
        dependencies.add(name)

    return dependencies


def filter_third_party_packages(names: set[str], project_root: Path) -> list[str]:
    """Filter import names down to likely third-party pip packages."""
    filtered: set[str] = set()
    for name in names:
        if not name or name.startswith("_"):
            continue
        if name in NEVER_PIP_INSTALL:
            continue
        if is_stdlib_module(name):
            continue
        if is_first_party_module(name, project_root):
            continue
        pkg_name = IMPORT_TO_PIP_PACKAGE.get(name, name)
        filtered.add(pkg_name)
    return sorted(filtered)


def pip_install_or_update(packages: Iterable[str], progress_callback: Callable[[str], None] | None = None) -> bool:
    """Install or update the given packages using pip.

    Args:
        packages: Package names to install or update
        progress_callback: Optional callback to report progress messages

    Returns:
        True when the pip command succeeds.
    """
    package_list = sorted(set(packages))
    if not package_list:
        return True

    if progress_callback:
        progress_callback(f"Installing {len(package_list)} package(s)...")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *package_list]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if progress_callback:
            progress_callback("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as exc:
        if progress_callback:
            progress_callback(f"Failed to install dependencies: {exc}")
        return False


def _marker_path(root: Path) -> Path:
    """Return the marker file path used to remember dependency checks."""
    try:
        import platformdirs  # type: ignore

        config_dir = Path(platformdirs.user_config_dir("ghostline", "ghostline"))
        return config_dir / "dep_check_done"
    except Exception:
        return root / ".ghostline_dep_check_done"


def should_run_dep_check(root: Path) -> bool:
    """Determine whether dependency checks should run."""
    if os.environ.get("GHOSTLINE_SKIP_DEP_CHECK"):
        return False

    if os.environ.get("GHOSTLINE_DEP_CHECK_ONCE"):
        marker = _marker_path(root)
        if marker.exists():
            return False

    return True


def mark_dep_check_done(root: Path) -> None:
    """Write the marker file indicating dependency checks have run."""
    marker = _marker_path(root)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch(exist_ok=True)
    except OSError:
        pass


def run_dependency_setup(progress_callback: Callable[[str], None] | None = None) -> bool:
    """Main entry point for dependency setup with progress reporting.

    Args:
        progress_callback: Optional callback that receives progress messages

    Returns:
        True on success, False on failure
    """
    root = project_root()

    if not should_run_dep_check(root):
        if progress_callback:
            progress_callback("Dependency check skipped")
        return True

    try:
        if progress_callback:
            progress_callback("Scanning project for dependencies...")

        names = collect_dependencies(root)
        packages = filter_third_party_packages(names, root)
    except Exception as exc:
        if progress_callback:
            progress_callback(f"Failed to collect dependencies: {exc}")
        return False

    if not packages:
        if progress_callback:
            progress_callback("No dependencies to install")
        if os.environ.get("GHOSTLINE_DEP_CHECK_ONCE"):
            mark_dep_check_done(root)
        return True

    if progress_callback:
        progress_callback(f"Found {len(packages)} package(s) to check...")

    try:
        success = pip_install_or_update(packages, progress_callback)
        if success and os.environ.get("GHOSTLINE_DEP_CHECK_ONCE"):
            mark_dep_check_done(root)
        return success
    except Exception as exc:
        if progress_callback:
            progress_callback(f"Dependency installation error: {exc}")
        return False
