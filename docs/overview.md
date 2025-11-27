# Ghostline Studio Overview

Ghostline Studio is an extensible code editor built with PySide6. Phase 2 adds
project awareness, language server support for Python, AI stubs, and a more
capable editor experience.

## Current Features

- Tabbed editor with line numbers, indentation helpers, and simple Python syntax highlighting.
- Workspace-backed project explorer tree and diagnostics dock.
- Python Language Server Protocol integration (tested with `pylsp`).
- Embedded terminal dock plus an external terminal launcher.
- Command palette powered by a registry of common commands.
- AI dock and commands backed by a dummy client for now.

## Requirements

- Python 3.10+
- PySide6
- Python language server (`pylsp`) available on PATH for LSP features.

## Running Ghostline

```
python -m ghostline.main [path]
```

Pass a file or folder to load it immediately. Use the File menu or command
palette to open additional files or folders.

## Enabling an AI backend

The included AI features use a dummy backend that echoes prompts. Configure your
preferred backend and endpoint via the Settings dialog or by editing
`~/.config/ghostline/settings.yaml` to point to your service. The AI chat dock
and commands will send prompts through the configured backend.
