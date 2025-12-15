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
  - Code folding with visual indicators
  - Folding infrastructure
- Document sync with the LSP system
- Editor events exposed for plugins and agents
- AI-powered inline suggestions with proactive code assistance
- Thread-safe AI suggestion cards with real-time updates

### Workspace & Navigation
- **Windsurf-style Welcome Portal** - Modern welcome screen with quick actions
  - Quick access shortcuts for common operations
  - Keyboard shortcut hints and discoverable commands
  - Clean, centered design for improved user experience
- Workspace-aware project explorer dock backed by a filesystem model
- Diagnostics dock driven by LSP publishDiagnostics events
- Command palette with fuzzy search across commands, files, and symbols
- **Persistent UI State** - Dock and widget state preservation across sessions
  - Window geometry and position persistence
  - Dock layout and visibility state restoration
  - Splitter positions and panel sizes remembered
- Activity bar for quick navigation between features
- Workspace dashboard for project overview

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
- Backend-agnostic (supports pyright, pylsp, or any compliant server)

### Embedded Terminal
- **Windsurf-style terminal dock** with modern UI design
- Multiple terminal session management with tabs
- PTY (pseudo-terminal) support for true terminal emulation
- Advanced interrupt handling (Ctrl+C) with echo suppression
- Cross-platform terminal widget backed by `QProcess` and PTY
- Shell selection, interactive input, and ANSI color output support
- Integrated bottom panel system with session switching
- Terminal profile management with customizable shells
- Resource-bundled terminal icons for consistent UI
- Clear output and kill session capabilities
- Dockable within the UI with persistent state

### Command System
- Global command registry
- Fuzzy-searchable command palette
- Commands attachable to menus, UI actions, shortcuts, plugins, and agents
- Structured command definitions with metadata and context support

### AI System
Ghostline Studio includes a multi-agent AI architecture designed for code reasoning, indexing, and workflow automation:

- **Persistent Chat History** - Save, load, and manage chat sessions across application restarts
  - Session storage with JSON-based persistence
  - Full message history with context preservation
  - Chat session management (create, update, delete)
  - Index-based session discovery and loading
- **Model Registry and Discovery** - Automatic discovery and management of AI models
  - OpenAI model support (GPT-5.1, GPT-4.1, and variants)
  - Ollama model auto-discovery via HTTP and CLI
  - Model provider abstraction for extensibility
  - Model metadata and capability tracking
- **Proactive AI Suggestions** - Context-aware code suggestions displayed as cards
  - Thread-safe suggestion delivery
  - Real-time suggestion updates
  - Multiple suggestion card display with scrolling
  - Comprehensive debugging and error handling
- Agent graph and orchestration (`ghostline/agents`)
- Workflow engine for multi-step operations (`ghostline/workflows`)
- Retrieval and semantic indexing system (`ghostline/semantic`)
- Task execution system for tool-augmented agent behavior (`ghostline/tasks`)
- Embeddings, search, chunking, and memory stores
- Pluggable AI backends with automatic fallback
- Chat interface integrated with the editor
- Workspace indexer and context engine that stitch together open buffers, recent semantic updates, and pinned snippets for AI prompts
- AI chat dock shows the context that will be used for a response, supports pinning active documents, and allows custom instructions per workspace session
- Architecture assistant for code navigation and analysis
- AI-powered refactor pipeline with patch parsing and application
- Maintenance daemon for background AI tasks

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

### Testing & Quality Assurance
- **Test Manager** - Integrated test execution and management
- **Test Panel** - Visual test runner interface
- **Coverage Panel** - Code coverage tracking and visualization
- Test integration with pytest
- AST integrity verification tests
- Core component testing infrastructure

### CRDT Engine (Experimental)
- Early CRDT implementation for collaborative editing
- Merge logic, serialization, and test coverage
- Collaborative panel for real-time editing sessions
- Session manager for multi-user collaboration

### Build & Formatting
- **Build System Integration** - Build panel for project compilation
- **Formatter Manager** - Code formatting with LSP integration
- Multi-server LSP chains for specialized formatting
- Pipeline manager for build workflows

### Runtime & Debugging
- **Runtime Panel** - Runtime environment monitoring
- **Debugger Manager** - Debug Adapter Protocol foundation
- Future DAP integration for multi-language debugging

### 3D Visualization (Experimental)
- `visual3d` subsystem for agent-assisted data visualizations
- Supports 3D scene models and rendering hooks

### Additional UI Components
- **Splash Screen** - Branded application startup screen
- **Status Bar** - Real-time status indicators
- **Custom Tab Bar** - Enhanced tab management
- **Panel Widgets** - Reusable UI components for consistent design
- **Dialog System** - Plugin manager and settings dialogs
- **Layout Manager** - Advanced layout management and persistence

---

## Project Structure

```
ghostline/
    app.py                – application bootstrap and initialization
    main.py               – entry point
    agents/               – multi-agent AI architecture and orchestration
    ai/                   – AI clients, chat panel, model registry, chat history
    core/                 – config loading, logging, utilities, theme, cache
    editor/               – CodeEditor, document system, and folding
    lang/                 – LSP engine and protocol logic (client, manager)
    workspace/            – workspace and project management
    terminal/             – embedded terminal (PTY, Windsurf-style UI)
    ui/                   – interface components and docks
        dialogs/          – plugin manager, settings, and other dialogs
        docks/            – all dock panels (terminal, build, tests, etc.)
        editor/           – editor-specific UI components
    plugins/              – plugin loader and registry
    tasks/                – tool/task execution for agents
    semantic/             – embeddings, semantic indexing, and retrieval
    search/               – indexing and search engine
    runtime/              – low-level runtime utilities
    vcs/                  – version control helpers (Git service)
    visual3d/             – 3D visualization components
    workflows/            – workflow engine and pipeline manager
    testing/              – test manager, test panel, coverage tracking
    build/                – build system integration
    formatter/            – code formatting and formatter manager
    debugger/             – debugger adapter protocol foundation
    collab/               – CRDT engine and session manager
    indexer/              – code indexing and index manager
    settings/             – default settings and configuration
    resources/            – bundled icons, themes, and assets
docs/
    architecture/         – design docs (LSP chains, AI pipeline, CRDT, DAP, plugins)
    plugins.md            – plugin development guide
    overview.md           – high-level overview
tests/                    – comprehensive test suite
    test_chat_history.py  – chat history persistence tests
    test_ai_client.py     – AI client tests
    test_core_*.py        – core component tests
    test_semantic_*.py    – semantic indexing tests
```

---

## Running Ghostline Studio

### Requirements
- Python 3.10+
- PySide6
- Optional: `openai` Python client for the OpenAI backend
- Optional: an LSP server (`pyright`, `pylsp`, etc.)
- Optional: an AI backend (local or remote)

### Launch

```bash
python -m ghostline.main [path]
```

`path` may be a file or directory to open on startup.

> Default LSP settings expect `pyright-langserver` on your `PATH`. Configure alternate language servers in `ghostline/settings/defaults.yaml` or your user settings file.

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

Expected endpoints match the defaults in `ghostline/settings/defaults.yaml`: `ai.endpoint` and `providers.ollama.host` should point to an Ollama-compatible server exposing `/api/generate`, while `ai.openai_endpoint` or `providers.openai.base_url` should be the OpenAI Responses-compatible base URL ending with `/v1`. Ghostline will surface clear messages for 401/404 responses suggesting API key or path fixes, and if those errors repeat in a session the client automatically falls back to the dummy echo backend so the AI dock stays usable until the configuration is corrected.

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
