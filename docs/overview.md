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
and commands will send prompts through the configured backend. For local
Ollama setups, Ghostline will attempt to auto-start the server with
`ollama serve` when needed (controlled by `ai.auto_start_ollama`). You can
still start it manually before launch, and use the `ai.timeout_seconds` setting
to accommodate slower hardware or cold model loads.

## 3D Architecture Map

Ghostline Studio now includes an early "Ghostline Spatial Map" for exploring the semantic structure of an open workspace. Open it from **View → 3D Architecture Map**. The dock shows modules, files, and functions as colored shapes with dependency lines and supports basic orbit/zoom camera controls. Clicking file or function nodes opens the corresponding file in the editor. Rendering uses Qt3D when available in your PySide6 build; otherwise a placeholder panel appears until OpenGL rendering is added.
