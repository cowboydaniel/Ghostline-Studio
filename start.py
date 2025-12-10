"""Bootstrap script to install dependencies and launch Ghostline Studio."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Core dependencies required by Ghostline Studio.
DEPENDENCIES = [
    "PySide6",
    "shiboken6",
    "PyYAML",
    "httpx",
    "openai",
]


def install_dependencies() -> None:
    """Install required packages using pip with --break-system-packages."""
    base_cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages"]
    for package in DEPENDENCIES:
        subprocess.check_call(base_cmd + [package])


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    install_dependencies()

    from ghostline.main import main as run_main

    raise SystemExit(run_main())


if __name__ == "__main__":
    main()
