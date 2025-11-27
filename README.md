# Ghostline Studio

Ghostline Studio is a modular, AI-augmented code editor concept built with PySide6.
Phase 2 turns the scaffold into a usable editor with a project explorer, Python LSP
support, an embedded terminal, and AI-ready UI components.

## Current Features

- Tabbed code editor with line numbers, indentation helpers, and basic Python syntax highlighting.
- Project explorer dock backed by the filesystem.
- Python Language Server support for diagnostics and hover requests.
- Embedded terminal and command palette with searchable commands.
- AI chat dock and commands powered by a dummy backend (ready for custom backends).
- Settings dialog for common editor, AI, and LSP options.

## Requirements

- Python 3.10+
- PySide6
- A Python LSP server (`pylsp`) available on your PATH for language features.

## Running

```
python -m ghostline.main [path]
```

Pass a file or folder path to open it on startup. The default theme is a dark
Fusion palette and the editor uses JetBrains Mono if available.

## How to enable AI backend

The bundled dummy backend echoes prompts. To wire in a real service, update the
`ai` section of your settings (via the Settings dialog or `~/.config/ghostline/settings.yaml`)
with your backend type and endpoint. The AI chat dock and commands will route
requests through whatever backend is configured.

## Project layout

- `ghostline/main.py` – entry point for launching the Qt application.
- `ghostline/app.py` – sets up configuration, theming, the main window, and optional startup paths.
- `ghostline/core/` – configuration loading, logging, and theme helpers.
- `ghostline/ui/` – main window, command palette, status bar, and tabbed editor container.
- `ghostline/editor/` – enhanced `CodeEditor` widget with line numbers, indentation, and highlighting.
- `ghostline/workspace/` – workspace manager, file tree model, and view.
- `ghostline/terminal/` – embedded terminal plus external launch helper.
- `ghostline/lang/` – LSP client/manager and diagnostics model.
- `ghostline/vcs/` – lightweight git helpers for branch and dirty status indicators.
- `ghostline/settings/` – default YAML settings and keybinding examples.

Ghostline Studio remains a work-in-progress, but the current build is usable for
Python editing with diagnostics, workspace browsing, and AI stubs.
