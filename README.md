# Ghostline Studio

Ghostline Studio is a modular, AI-augmented code editor concept built with PySide6.
This repository currently provides a lightweight scaffold with the core
application frame, editor tabs, a command palette, workspace tracking, and a
placeholder terminal dock.

## Running

```
python -m ghostline.main [path]
```

Pass a file or folder path to open it on startup. The default theme is a dark
Fusion palette and the editor uses JetBrains Mono if available.

## Project layout

- `ghostline/main.py` – entry point for launching the Qt application.
- `ghostline/app.py` – sets up configuration, theming, the main window, and optional startup paths.
- `ghostline/core/` – configuration loading, logging, and theme helpers.
- `ghostline/ui/` – main window, command palette, status bar, and tabbed editor container.
- `ghostline/editor/` – minimal `CodeEditor` widget based on `QPlainTextEdit`.
- `ghostline/workspace/` – workspace manager with simple recents persistence.
- `ghostline/terminal/` – placeholder widget that opens the system terminal in the workspace.
- `ghostline/vcs/` – lightweight git helpers for branch and dirty status indicators.
- `ghostline/settings/` – default YAML settings and keybinding examples.

This scaffold is intended as a starting point for implementing the broader
Ghostline Studio roadmap (LSP integration, AI assistance, plugin system, etc.).
