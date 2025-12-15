# Ghostline Studio Overview

Ghostline Studio is a comprehensive, AI-augmented development environment built with PySide6.
It combines modern IDE features with advanced AI capabilities, providing a powerful platform
for code editing, analysis, and collaboration.

## Current Features

### Editor & Workspace
- **Advanced Code Editor** with line numbers, indentation helpers, syntax highlighting, and code folding
- **Tabbed Interface** with multi-document management and smart tab bar
- **Workspace Management** - Project explorer tree with file watching and change signaling
- **Windsurf-style Welcome Portal** - Modern onboarding with quick actions and keyboard shortcuts
- **Persistent UI State** - Dock layouts, window geometry, and panel positions saved across sessions
- **Command Palette** - Fuzzy search across commands, files, and symbols (Ctrl+Shift+P)
- **Activity Bar** - Quick navigation between editor features
- **Status Bar** - Real-time status indicators and notifications

### Language Intelligence
- **Language Server Protocol (LSP)** - Full integration with Python language servers (pyright, pylsp)
- **Diagnostics Panel** - Real-time error and warning display driven by LSP
- **Multi-server LSP Chains** - Support for multiple LSP servers per language with role separation
- **Code Navigation** - Go to definition, hover information, and symbol search
- **Code Formatting** - Formatter manager with LSP integration

### Terminal & Build System
- **Windsurf-style Terminal Dock** - Modern terminal with tabbed sessions
- **PTY Terminal Support** - True pseudo-terminal emulation for better shell interaction
- **Multiple Terminal Sessions** - Create and manage multiple terminal instances
- **Advanced Interrupt Handling** - Proper Ctrl+C handling with echo suppression
- **Terminal Profiles** - Customizable shell selection and preferences
- **Build Panel** - Integrated build system for project compilation
- **Pipeline Manager** - Workflow orchestration for complex build processes

### AI & Intelligence
- **Persistent Chat History** - Save and restore AI chat sessions across application restarts
- **Model Registry** - Automatic discovery of OpenAI and Ollama models
- **AI Chat Panel** - Context-aware AI assistance with workspace integration
- **Proactive Suggestions** - AI suggestion cards with thread-safe delivery
- **Context Engine** - Intelligent context gathering from workspace and editor state
- **Semantic Search** - Advanced code search using embeddings and semantic indexing
- **Architecture Assistant** - AI-powered code navigation and analysis
- **Refactor Pipeline** - AI-driven code refactoring with patch application
- **Multi-Agent System** - Agent orchestration for complex workflows
- **Workspace Memory** - Persistent memory across AI sessions

### Testing & Quality
- **Test Manager** - Integrated test execution and management
- **Test Panel** - Visual test runner with pytest integration
- **Coverage Panel** - Code coverage tracking and visualization
- **AST Integrity Tests** - Automated verification of code structure

### Collaboration (Experimental)
- **CRDT Engine** - Conflict-free replicated data types for collaborative editing
- **Session Manager** - Multi-user session coordination
- **Collaborative Panel** - Real-time collaborative editing interface

### 3D Visualization & Analysis
- **Ghostline Spatial Map** - 3D architecture visualization (View → 3D Architecture Map)
- **Interactive Graph Navigation** - Click nodes to open files and functions
- **Qt3D Rendering** - Hardware-accelerated 3D scenes with orbit/zoom controls
- **Dependency Visualization** - Visual representation of code relationships
- **Architecture Panel** - Analysis and visualization of project structure

### Plugin System
- **Dynamic Plugin Loading** - Load plugins from bundled and user directories
- **Plugin Registry** - Centralized plugin management and discovery
- **Extension Points** - Extend commands, panels, LSP chains, and AI tools
- **Plugin Manager Dialog** - Enable/disable plugins through UI
- **Plugin Metadata** - YAML-based plugin configuration with versioning

### Version Control
- **Git Service** - Integrated Git operations and status tracking
- **VCS Integration** - Version control awareness throughout the UI

### Additional Components
- **Splash Screen** - Branded startup screen with progress indicators
- **Dialog System** - Consistent dialogs for settings and plugin management
- **Layout Manager** - Advanced layout persistence and restoration
- **Theme System** - Customizable themes with resource bundling
- **Cache System** - Performance optimization through intelligent caching
- **Self-Healing** - Automatic recovery and error handling
- **Logging System** - Comprehensive logging for debugging and monitoring

## Requirements

- Python 3.10+
- PySide6
- Optional: Python language server (`pyright` or `pylsp`) for LSP features
- Optional: OpenAI API key or local Ollama installation for AI features

## Running Ghostline

```bash
python -m ghostline.main [path]
```

Pass a file or folder to load it immediately. Use the File menu or command
palette to open additional files or folders.

## Enabling an AI backend

The included AI features use a dummy backend that echoes prompts by default. Configure your
preferred backend and endpoint via the Settings dialog or by editing
`~/.config/ghostline/settings.yaml` to point to your service.

### Supported AI Providers
- **OpenAI** - GPT-5.1, GPT-4.1, and variants
- **Ollama** - Local model support with auto-discovery
- **Custom Endpoints** - Compatible with OpenAI API format

The AI chat dock and commands will send prompts through the configured backend. For local
Ollama setups, Ghostline will attempt to auto-start the server with
`ollama serve` when needed (controlled by `ai.auto_start_ollama`). You can
still start it manually before launch, and use the `ai.timeout_seconds` setting
to accommodate slower hardware or cold model loads.

## 3D Architecture Map

Ghostline Studio includes the "Ghostline Spatial Map" for exploring the semantic structure of an open workspace. Open it from **View → 3D Architecture Map**. The dock shows modules, files, and functions as colored shapes with dependency lines and supports basic orbit/zoom camera controls. Clicking file or function nodes opens the corresponding file in the editor. Rendering uses Qt3D when available in your PySide6 build; otherwise a placeholder panel appears until OpenGL rendering is added.

## Configuration

Ghostline loads configuration from:
1. Default settings in `ghostline/settings/defaults.yaml`
2. User settings in `~/.config/ghostline/settings.yaml`

### Key Configuration Areas
- **Editor** - Tab size, font, folding behavior
- **AI** - Model selection, API keys, context limits
- **LSP** - Language server configuration and chains
- **Terminal** - Shell selection, profiles, appearance
- **Theme** - Color schemes and UI styling
- **Plugins** - Enable/disable plugins and extensions

## Keyboard Shortcuts

- **Ctrl+Shift+P** - Open Command Palette
- **Ctrl+L** - Open AI Chat
- **Ctrl+K Ctrl+O** - Open Folder
- **Ctrl+C** (Terminal) - Interrupt running process
- Additional shortcuts available in the Command Palette

## Getting Help

- Check the `/docs` folder for detailed documentation
- View `AGENTS.md` for AI agent development guidelines
- See `docs/plugins.md` for plugin development
- Browse `docs/architecture/` for system design documents
