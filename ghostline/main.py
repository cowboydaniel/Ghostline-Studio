"""
Ghostline Studio entry point.
"""
from __future__ import annotations

from ghostline.app import GhostlineApplication


def main() -> int:
    app = GhostlineApplication()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
