"""Bootstrap script to ensure dependencies are available and launch Ghostline Studio."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Iterable, Set


def project_root() -> Path:
    """Return the absolute path to the repository root."""

    return Path(__file__).resolve().parent


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
    platstdlib_path = Path(sysconfig.get_paths().get("platstdlib", stdlib_path)).resolve()
    try:
        origin = Path(spec.origin).resolve()
    except OSError:
        return True

    stdlib_roots = [stdlib_path, platstdlib_path]

    if sys.platform == "win32":
        dlls_dir = stdlib_path.parent / "DLLs"
        stdlib_roots.append(dlls_dir)

    for root in stdlib_roots:
        try:
            origin.relative_to(root)
            return True
        except ValueError:
            continue

    return False


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
    "select",
}

# Platform-specific modules that should never trigger pip installation.
PLATFORM_NEVER_PIP_INSTALL = {
    "win32": {"fcntl"},
}

# PySide6 currently publishes Windows wheels for Python versions earlier than
# 3.14. Windows users frequently install the embeddable Python 3.14
# distribution, which will fail to resolve a compatible PySide6 release. We
# gate dependency installation so we can surface a clear message instead of a
# confusing pip resolution error.
PYSIDE6_WINDOWS_MAX_SUPPORTED = (3, 14)

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
    platform_blocklist = PLATFORM_NEVER_PIP_INSTALL.get(sys.platform, set())
    for name in names:
        if not name or name.startswith("_"):
            continue
        if name in NEVER_PIP_INSTALL:
            continue
        if name in platform_blocklist:
            continue
        if is_stdlib_module(name):
            continue
        if is_first_party_module(name, project_root):
            continue
        pkg_name = IMPORT_TO_PIP_PACKAGE.get(name, name)
        filtered.add(pkg_name)
    return sorted(filtered)


def _pyside_supported() -> bool:
    """Return ``True`` if the current interpreter can install PySide6."""

    if sys.platform != "win32":
        return True

    return sys.version_info < PYSIDE6_WINDOWS_MAX_SUPPORTED


def pip_install_or_update(packages: Iterable[str]) -> bool:
    """Install or update the given packages using pip.

    Returns ``True`` when the pip command succeeds.
    """

    package_list = sorted(set(packages))
    if not package_list:
        return True

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *package_list]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"[Ghostline] Failed to install/update dependencies: {exc}", file=sys.stderr)
        return False
    return True


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
    except OSError as exc:
        print(f"[Ghostline] Unable to record dependency check marker: {exc}", file=sys.stderr)


def ensure_dependencies_installed() -> None:
    """Discover and install required dependencies, handling failures gracefully."""

    root = project_root()
    if not should_run_dep_check(root):
        return

    try:
        names = collect_dependencies(root)
        packages = filter_third_party_packages(names, root)
    except Exception as exc:
        print(f"[Ghostline] Failed to collect dependencies: {exc}", file=sys.stderr)
        return

    if "PySide6" in packages and not _pyside_supported():
        print(
            "[Ghostline] PySide6 wheels are not available for Python 3.14 yet. "
            "Please install Python 3.13 or earlier on Windows to run Ghostline "
            "Studio.",
            file=sys.stderr,
        )
        return

    if not packages:
        if os.environ.get("GHOSTLINE_DEP_CHECK_ONCE"):
            mark_dep_check_done(root)
        return

    print("[Ghostline] Checking Python dependencies...", file=sys.stderr)
    try:
        success = pip_install_or_update(packages)
        if success:
            print("[Ghostline] Dependency check complete.", file=sys.stderr)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[Ghostline] Dependency installation encountered an error: {exc}", file=sys.stderr)
    finally:
        if os.environ.get("GHOSTLINE_DEP_CHECK_ONCE"):
            mark_dep_check_done(root)


def launch_ghostline() -> None:
    """Launch the Ghostline application."""

    root = project_root()
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from ghostline.main import main as run_main

    raise SystemExit(run_main())


def main() -> None:
    # Ensure critical dependencies are installed before imports
    # This prevents import errors from blocking the splash screen
    ensure_dependencies_installed()
    launch_ghostline()


if __name__ == "__main__":
    main()
