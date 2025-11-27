"""
Ghostline Studio entry point.
"""
from __future__ import annotations

from pathlib import Path
import sys

# Allow running the file directly (e.g. `python ghostline/main.py`) by
# ensuring the repository root is on sys.path before importing the package.
if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from ghostline.app import GhostlineApplication


def main() -> int:
    app = GhostlineApplication()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
