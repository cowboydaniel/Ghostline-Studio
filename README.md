# Ghostline Studio

Ghostline Studio is a modular, extensible, AI-augmented development environment built with PySide6.
It provides a full editor workspace, language tooling, an embedded terminal, a plugin system, and a multi-agent AI pipeline designed for deep code understanding and automated workflows.

Ghostline Studio is structured as a platform: nearly every subsystem is modular, replaceable, and designed for extension.

---

## Features

### Code Editing
- Tabbed editor with multi-document management
- Custom `CodeEditor` widget with:
  - Line numbers
  - Indentation helpers
  - Syntax highlighting
  - Folding infrastructure
- Document sync with the LSP system
- Editor events exposed for plugins and agents

### Workspace & Navigation
- Workspace-aware project explorer dock backed by a filesystem model
- Diagnostics dock driven by LSP publishDiagnostics events
- Command palette with fuzzy search across commands, files, and symbols

### Architecture Map
- **Ghostline Spatial Map** dock (View → 3D Architecture Map)
- Qt3D-powered scene when available with orbit/zoom controls and clickable nodes
- Graceful placeholder when Qt3D is unavailable
- Opens files/functions when nodes are selected in the graph

### Workspace System
- `WorkspaceManager` for project-level handling
- Filesystem-backed tree model (`WorkspaceTree`, `WorkspaceNode`)
- File watching and change signaling
- Workspace metadata and state management

### Language Server Protocol (LSP)
- Modular LSP client using JSON-RPC
- Document open/close/update sync
- Diagnostics pipeline
- Hover information
- Formatting requests
- Definition/navigation hooks
- Backend-agnostic (supports pylsp, pyright, or any compliant server)

### Embedded Terminal
- Cross-platform terminal widget
- Backed by `QProcess`
- Shell selection, interactive input, and color output
- Dockable within the UI

### Command System
- Global command registry
- Fuzzy-searchable command palette
- Commands attachable to menus, UI actions, shortcuts, plugins, and agents
- Structured command definitions with metadata and context support

### AI System
Ghostline Studio includes a multi-agent AI architecture designed for code reasoning, indexing, and workflow automation:

- Agent graph and orchestration (`ghostline/agents`)
- Workflow engine for multi-step operations (`ghostline/workflows`)
- Retrieval and semantic indexing system (`ghostline/semantic`)
- Task execution system for tool-augmented agent behavior (`ghostline/tasks`)
- Embeddings, search, chunking, and memory stores
- Pluggable AI backends
- Chat interface integrated with the editor
- Workspace indexer and context engine that stitch together open buffers, recent semantic updates, and pinned snippets for AI prompts
- AI chat dock shows the context that will be used for a response, supports pinning active documents, and allows custom instructions per workspace session

### Plugin Architecture
- Plugin registry and dynamic loader (`ghostline/plugins`)
- Extension points for:
  - Commands
  - Panels and docks
  - LSP chain steps
  - Search and indexing
  - AI tools and workflows
- Architecture documented under `docs/architecture/plugin_system_v1.md`

### Search System
- Tokenization and indexing
- Semantic search
- File and project-wide queries
- Integration with agents and UI workflows

### CRDT Engine (Experimental)
- Early CRDT implementation for collaborative editing
- Merge logic, serialization, and test coverage under `ghostline/testing`

### 3D Visualization (Experimental)
- `visual3d` subsystem for agent-assisted data visualizations
- Supports 3D scene models and rendering hooks

---

## Project Structure

```
ghostline/
    app.py                – application bootstrap
    main.py               – entry point
    agents/               – multi-agent AI architecture
    core/                 – config loading, logging, utilities
    editor/               – CodeEditor and document system
    lang/                 – LSP engine and protocol logic
    workspace/            – workspace and project management
    terminal/             – embedded terminal subsystem
    ui/                   – interface components and docks
    plugins/              – plugin loader and registry
    tasks/                – tool/task execution for agents
    semantic/             – embeddings and retrieval
    search/               – indexing and search engine
    runtime/              – low-level runtime utilities
    vcs/                  – version control helpers
    visual3d/             – 3D visualization components
docs/
    architecture/         – design docs (LSP chains, AI pipeline, CRDT)
tests/                    – test suite
```

---

## Running Ghostline Studio

### Requirements
- Python 3.10+
- PySide6
- Optional: an LSP server (`pylsp`, `pyright`, etc.)
- Optional: an AI backend (local or remote)

### Launch

```bash
python -m ghostline.main [path]
```

`path` may be a file or directory to open on startup.

> Default LSP settings expect `pylsp` on your `PATH`. Configure alternate language servers in `ghostline/settings/defaults.yaml` or your user settings file.

---

## Configuration

Ghostline Studio loads configuration from:

1. Default settings in `ghostline/settings/`
2. User-level configuration:

```
~/.config/ghostline/settings.yaml
```

Configurable areas include:
- Editor behavior
- Theme
- AI backend and agent settings
- LSP options
- Terminal preferences
- Plugin settings

AI features default to a dummy backend that echoes prompts so the AI chat dock is immediately usable. To point Ghostline at your own service, update `~/.config/ghostline/settings.yaml` (or the Settings dialog) with your endpoint, model, and `ai.timeout_seconds` for slower local models such as Ollama. Start local Ollama instances with `ollama serve` before launching Ghostline if you select the Ollama backend.

Context retrieval settings live under the `ai` key:

```yaml
ai:
  max_context_chars: 1200  # Controls how much text each snippet contributes
  context_results: 5       # How many indexed files to pull into each prompt
```

---

## Extending Ghostline

### Plugins
Plugins can contribute:
- Commands
- UI components
- Agents and tools
- LSP pipeline steps
- Indexers and search handlers
- Workflow actions

Documentation:
`docs/architecture/plugin_system_v1.md`

### AI Workflows
Define new agents or multi-step workflows under:
- `ghostline/agents`
- `ghostline/tasks`
- `ghostline/workflows`

### LSP Backends
Configure any compliant LSP server via settings.

---

## Status

Ghostline Studio is under active development.
Core systems are functional, but several areas continue to evolve, including:

- AI tooling depth
- Plugin ecosystem maturity
- Collaborative editing (CRDT)
- Visual tooling and advanced UI components

Contributions and experimentation are welcome.
