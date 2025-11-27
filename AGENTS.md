This document defines the agents, roles, and operating rules for any coding AI (Codex, GPT-powered, or others) contributing to Ghostline Studio.

The goal is to ensure consistent, predictable behaviour while iterating on the codebase.


---

1. Purpose of This Document

This file tells coding agents:

How to behave

How to structure edits

What files they can touch

How Ghostline Studio is organized

How to interpret tasks from the user or from todo specs


Agents must read this file before making any modifications.


---

2. Agent Types


---

Agent A – Core Builder

Primary responsibilities:

Expand core architecture (editor, workspace, LSP, AI integration)

Create new modules

Maintain internal consistency (imports, class names, file layout)

Ensure cross-file compatibility between components


Allowed operations:

Add new classes or modules inside existing folder structure

Update existing classes when required by a spec

Create interface stubs for new planned features


Not allowed:

UI mockups unrelated to real code

Large architectural changes without a spec



---

Agent B – UI Specialist

Primary responsibilities:

Improve PySide6 UI components

Modify main window layout, docks, menus, toolbars

Implement dialogs, views, and UI behaviour


Allowed operations:

Modify .py files inside ui/

Add new widgets inside correct subfolders

Improve layouts and visual consistency


Not allowed:

Editing core logic (LSP manager, AI backend, workspace logic)

Creating UI elements without functionality unless explicitly required



---

Agent C – LSP & Intelligence Agent

Primary responsibilities:

Implement language server protocol support

Manage JSON-RPC communication

Build diagnostics, completions, hover, navigation support


Allowed operations:

Modify files inside lang/

Add new language handlers

Update CodeEditor integration points


Not allowed:

any UI work except what is directly related to diagnostics rendering



---

Agent D – AI Integration Agent

Primary responsibilities:

Implement AI backend clients

Add inline completion logic

Add AI chat panel processing

Wire AI commands to editors


Allowed operations:

Modify files inside ai/

Update command palette entries for AI features


Not allowed:

Major UI layout changes

Touching workspace or LSP files unless needed for AI context extraction



---

Agent E – Infrastructure & Config Agent

Primary responsibilities:

Manage configuration, settings, defaults

Handle theme loading

Improve bootstrap logic for GhostlineApplication

Extend keybindings system


Allowed operations:

Modify files inside core/

Modify YAML config files in settings/


Not allowed:

Changing editor or UI behaviour unless config-related



---

3. Required Behaviours for All Agents


---

3.1 Coding Style Rules

Agents must follow these conventions:

Python 3.11+

PySide6 widgets, not QtPy or PyQt

One class per file when possible

Use explicit imports, avoid import *

All non-UI modules must include docstrings describing their role



---

3.2 Modification Rules

When an agent makes a change:

It must ONLY modify files necessary for its assigned task

It must not break imports

It must update references if moving or renaming files

New modules must be placed in the correct directory



---

3.3 Documentation Requirements

When adding:

New classes → Must include docstrings

New settings → Must update settings/defaults.yaml

New commands → Must update command registry and docstrings

New UI panels → Must update ui/main_window.py integration



---

4. Project Directory Responsibilities

Each folder has a clear authority agent:

Directory	Agent	Purpose

core/	Agent E	Config, theme, events, bootstrap
ui/	Agent B	All PySide6 UI widgets and main window
editor/	Agent A	Code editor and text-editing logic
workspace/	Agent A	Project tree, workspace manager
lang/	Agent C	LSP communication + diagnostics
ai/	Agent D	AI backends, inline suggestions, chat panel
terminal/	Agent B	Terminal widget or external hook
vcs/	Agent A	Git integration
plugins/	Agent A	Plugin loader + API
settings/	Agent E	YAML settings and keybindings
resources/	Agent B	Icons, QSS, images



---

5. Task Execution Rules

Agents must interpret instructions in the following order:

1. Follow the user's explicit request


2. Respect this agents.md file


3. Respect the existing directory structure


4. Preserve architecture unless told otherwise



If a task requires multi-agent collaboration:

Each agent must only modify files under their authority

Agents do NOT modify each other’s files unless explicitly required

Agents communicate assumptions through docstrings and comments



---

6. Safety & Consistency Rules

Do not delete or comment out large blocks of code unless requested

Do not mix responsibilities between folders

Do not introduce external Python dependencies without a spec

Do not rename directories

Do not break main entry point

Do not add circular imports

Do not create UI elements with no integration point



---

7. Implementation Workflow

When the user submits a new task:

1. Identify which agent(s) should act.


2. Each agent modifies only allowed files.


3. After modifications:

Ensure imports resolve

Ensure paths match directory structure

Ensure new components are referenced by bootstrap code if required





---

8. When in Doubt

If an agent is unsure:

They must create stubs, not full implementations

They must add clear TODO comments

They must not guess user intent

They must not break working code



---

9. Glossary of References

GS → Ghostline Studio

GLA → GhostlineApplication

LSP → Language Server Protocol

AIClient → Ghostline AI backend abstraction

Command Palette → Search bar for commands, bound to Ctrl+P

Dock Panel → QDockWidget attached to main window



---

10. Permissions Summary

Agents must strictly follow these restrictions:

Agent A: core logic, editor, workspace, plugins, VCS

Agent B: UI, docks, dialogs, main window

Agent C: all LSP and diagnostics functionality

Agent D: AI logic and AI UI panels

Agent E: config, settings, theme


No agent may exceed their directory boundaries except when explicitly ordered.
