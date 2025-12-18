"""
Allow running Ghostline Studio as a module: python -m ghostline
"""
from ghostline.main import main

if __name__ == "__main__":
    raise SystemExit(main())
