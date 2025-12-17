"""Centralized action registry for Ghostline Studio.

This module provides a unified action management system that allows actions
to be shared across menus, command palettes, context menus, and titlebar dropdowns.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:
    from ghostline.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class ActionCategory(Enum):
    """Categories for organizing actions."""
    FILE = auto()
    EDIT = auto()
    SELECTION = auto()
    VIEW = auto()
    GO = auto()
    RUN = auto()
    TERMINAL = auto()
    HELP = auto()


@dataclass
class ActionSpec:
    """Specification for an action."""
    id: str
    label: str
    category: ActionCategory
    shortcut: str | None = None
    checkable: bool = False
    enabled_when: Callable[[], bool] | None = None
    icon: str | None = None
    tooltip: str | None = None


class ChordShortcut:
    """Helper class for chord shortcuts like Ctrl+K Ctrl+O."""

    def __init__(self, first: str, second: str):
        self.first = first
        self.second = second
        self._pending = False
        self._action: QAction | None = None
        self._window: MainWindow | None = None

    def display_string(self) -> str:
        return f"{self.first} {self.second}"

    def attach(self, action: QAction, window: MainWindow) -> None:
        """Attach the chord shortcut to an action."""
        self._action = action
        self._window = window
        # Set the first part as the shortcut
        action.setShortcut(QKeySequence(self.first))
        # Store reference for chord handling
        if not hasattr(window, '_chord_shortcuts'):
            window._chord_shortcuts = {}
        window._chord_shortcuts[self.first] = self


class ActionRegistry(QObject):
    """Centralized registry for all application actions."""

    def __init__(self, window: MainWindow):
        super().__init__(window)
        self.window = window
        self._actions: dict[str, QAction] = {}
        self._specs: dict[str, ActionSpec] = {}
        self._chord_shortcuts: dict[str, ChordShortcut] = {}
        self._state_trackers: dict[str, Callable[[], bool]] = {}

    def register(self, spec: ActionSpec, callback: Callable[[], None]) -> QAction:
        """Register an action with the given specification."""
        action = QAction(spec.label, self.window)
        action.setObjectName(spec.id)

        if spec.shortcut:
            if ' ' in spec.shortcut and not spec.shortcut.startswith('Shift+Alt+'):
                # Handle chord shortcuts
                parts = spec.shortcut.split(' ', 1)
                if len(parts) == 2:
                    chord = ChordShortcut(parts[0], parts[1])
                    chord.attach(action, self.window)
                    self._chord_shortcuts[parts[0]] = chord
                    # Set display text with full chord
                    action.setText(f"{spec.label}\t{spec.shortcut}")
            else:
                action.setShortcut(QKeySequence(spec.shortcut))

        if spec.checkable:
            action.setCheckable(True)

        if spec.tooltip:
            action.setToolTip(spec.tooltip)

        if spec.icon:
            from ghostline.core.resources import load_icon
            action.setIcon(load_icon(spec.icon))

        action.triggered.connect(callback)

        if spec.enabled_when:
            self._state_trackers[spec.id] = spec.enabled_when

        self._actions[spec.id] = action
        self._specs[spec.id] = spec

        return action

    def get(self, action_id: str) -> QAction | None:
        """Get an action by its ID."""
        return self._actions.get(action_id)

    def update_states(self) -> None:
        """Update enabled/disabled states for all actions."""
        for action_id, checker in self._state_trackers.items():
            action = self._actions.get(action_id)
            if action:
                try:
                    action.setEnabled(checker())
                except Exception:
                    logger.exception(f"Error checking state for action {action_id}")
                    action.setEnabled(False)

    def all_actions(self) -> list[QAction]:
        """Return all registered actions."""
        return list(self._actions.values())

    def actions_by_category(self, category: ActionCategory) -> list[QAction]:
        """Return actions for a specific category."""
        return [
            self._actions[spec.id]
            for spec in self._specs.values()
            if spec.category == category and spec.id in self._actions
        ]


def create_all_actions(window: MainWindow, registry: ActionRegistry) -> None:
    """Create and register all application actions."""

    # Helper functions for state checking
    def has_editor() -> bool:
        return window.get_current_editor() is not None

    def has_workspace() -> bool:
        return window.workspace_manager.current_workspace is not None

    def has_modified_editor() -> bool:
        editor = window.get_current_editor()
        return editor is not None and editor.document().isModified()

    def has_selection() -> bool:
        editor = window.get_current_editor()
        return editor is not None and editor.textCursor().hasSelection()

    def debugger_running() -> bool:
        return window.debugger.is_running() if hasattr(window, 'debugger') else False

    def debugger_paused() -> bool:
        return window.debugger.is_paused() if hasattr(window, 'debugger') else False

    def always_enabled() -> bool:
        return True

    # ========== FILE MENU ACTIONS ==========

    registry.register(
        ActionSpec("file.new_text_file", "New Text File", ActionCategory.FILE, "Ctrl+N"),
        window._new_text_file
    )

    registry.register(
        ActionSpec("file.new_file", "New File...", ActionCategory.FILE, "Ctrl+Alt+Super+N"),
        window._new_file_dialog
    )

    registry.register(
        ActionSpec("file.new_window", "New Window", ActionCategory.FILE, "Ctrl+Shift+N"),
        window._new_window
    )

    registry.register(
        ActionSpec("file.open_file", "Open File...", ActionCategory.FILE, "Ctrl+O"),
        window._prompt_open_file
    )

    registry.register(
        ActionSpec("file.open_folder", "Open Folder...", ActionCategory.FILE, "Ctrl+K Ctrl+O"),
        window._prompt_open_folder
    )

    registry.register(
        ActionSpec("file.open_workspace", "Open Workspace from File...", ActionCategory.FILE),
        window._open_workspace_file
    )

    registry.register(
        ActionSpec("file.add_folder", "Add Folder to Workspace...", ActionCategory.FILE),
        window._add_folder_to_workspace
    )

    registry.register(
        ActionSpec("file.save_workspace_as", "Save Workspace As...", ActionCategory.FILE),
        window._save_workspace_as
    )

    registry.register(
        ActionSpec("file.duplicate_workspace", "Duplicate Workspace", ActionCategory.FILE, enabled_when=has_workspace),
        window._duplicate_workspace
    )

    registry.register(
        ActionSpec("file.save", "Save", ActionCategory.FILE, "Ctrl+S", enabled_when=has_editor),
        window._save_current_file
    )

    registry.register(
        ActionSpec("file.save_as", "Save As...", ActionCategory.FILE, "Ctrl+Shift+S", enabled_when=has_editor),
        window._save_as
    )

    registry.register(
        ActionSpec("file.save_all", "Save All", ActionCategory.FILE),
        window.save_all
    )

    registry.register(
        ActionSpec("file.auto_save", "Auto Save", ActionCategory.FILE, checkable=True),
        window._toggle_auto_save
    )

    registry.register(
        ActionSpec("file.revert", "Revert File", ActionCategory.FILE, enabled_when=has_editor),
        window._revert_file
    )

    registry.register(
        ActionSpec("file.close_editor", "Close Editor", ActionCategory.FILE, "Ctrl+W", enabled_when=has_editor),
        window._close_current_editor
    )

    registry.register(
        ActionSpec("file.close_folder", "Close Folder", ActionCategory.FILE, "Ctrl+K F", enabled_when=has_workspace),
        window._close_folder
    )

    registry.register(
        ActionSpec("file.close_window", "Close Window", ActionCategory.FILE, "Alt+F4"),
        window.close
    )

    registry.register(
        ActionSpec("file.exit", "Exit", ActionCategory.FILE, "Ctrl+Q"),
        window._exit_application
    )

    # ========== EDIT MENU ACTIONS ==========

    registry.register(
        ActionSpec("edit.undo", "Undo", ActionCategory.EDIT, "Ctrl+Z", enabled_when=has_editor),
        lambda: window._with_editor(lambda e: e.undo())
    )

    registry.register(
        ActionSpec("edit.redo", "Redo", ActionCategory.EDIT, "Ctrl+Y", enabled_when=has_editor),
        lambda: window._with_editor(lambda e: e.redo())
    )

    registry.register(
        ActionSpec("edit.cut", "Cut", ActionCategory.EDIT, "Ctrl+X", enabled_when=has_selection),
        lambda: window._with_editor(lambda e: e.cut())
    )

    registry.register(
        ActionSpec("edit.copy", "Copy", ActionCategory.EDIT, "Ctrl+C", enabled_when=has_selection),
        lambda: window._with_editor(lambda e: e.copy())
    )

    registry.register(
        ActionSpec("edit.paste", "Paste", ActionCategory.EDIT, "Ctrl+V", enabled_when=has_editor),
        lambda: window._with_editor(lambda e: e.paste())
    )

    registry.register(
        ActionSpec("edit.find", "Find", ActionCategory.EDIT, "Ctrl+F", enabled_when=has_editor),
        window._open_find_dialog
    )

    registry.register(
        ActionSpec("edit.replace", "Replace", ActionCategory.EDIT, "Ctrl+H", enabled_when=has_editor),
        window._open_replace_dialog
    )

    registry.register(
        ActionSpec("edit.find_in_files", "Find in Files", ActionCategory.EDIT, "Ctrl+Shift+F"),
        window._open_global_search
    )

    registry.register(
        ActionSpec("edit.replace_in_files", "Replace in Files", ActionCategory.EDIT, "Ctrl+Shift+H"),
        window._open_global_replace
    )

    registry.register(
        ActionSpec("edit.toggle_line_comment", "Toggle Line Comment", ActionCategory.EDIT, "Ctrl+/", enabled_when=has_editor),
        window._toggle_line_comment
    )

    registry.register(
        ActionSpec("edit.toggle_block_comment", "Toggle Block Comment", ActionCategory.EDIT, "Ctrl+Shift+A", enabled_when=has_editor),
        window._toggle_block_comment
    )

    registry.register(
        ActionSpec("edit.emmet_expand", "Emmet: Expand Abbreviation", ActionCategory.EDIT, "Tab", enabled_when=has_editor),
        window._emmet_expand
    )

    # ========== SELECTION MENU ACTIONS ==========

    registry.register(
        ActionSpec("selection.select_all", "Select All", ActionCategory.SELECTION, "Ctrl+A", enabled_when=has_editor),
        lambda: window._with_editor(lambda e: e.selectAll())
    )

    registry.register(
        ActionSpec("selection.expand", "Expand Selection", ActionCategory.SELECTION, "Shift+Alt+RightArrow", enabled_when=has_editor),
        window._expand_selection
    )

    registry.register(
        ActionSpec("selection.shrink", "Shrink Selection", ActionCategory.SELECTION, "Shift+Alt+LeftArrow", enabled_when=has_editor),
        window._shrink_selection
    )

    registry.register(
        ActionSpec("selection.copy_line_up", "Copy Line Up", ActionCategory.SELECTION, "Ctrl+Shift+Alt+UpArrow", enabled_when=has_editor),
        window._copy_line_up
    )

    registry.register(
        ActionSpec("selection.copy_line_down", "Copy Line Down", ActionCategory.SELECTION, "Ctrl+Shift+Alt+DownArrow", enabled_when=has_editor),
        window._copy_line_down
    )

    registry.register(
        ActionSpec("selection.move_line_up", "Move Line Up", ActionCategory.SELECTION, "Alt+UpArrow", enabled_when=has_editor),
        window._move_line_up
    )

    registry.register(
        ActionSpec("selection.move_line_down", "Move Line Down", ActionCategory.SELECTION, "Alt+DownArrow", enabled_when=has_editor),
        window._move_line_down
    )

    registry.register(
        ActionSpec("selection.duplicate", "Duplicate Selection", ActionCategory.SELECTION, "Alt+Shift+DownArrow", enabled_when=has_editor),
        window._duplicate_selection
    )

    registry.register(
        ActionSpec("selection.add_cursor_above", "Add Cursor Above", ActionCategory.SELECTION, "Shift+Alt+UpArrow", enabled_when=has_editor),
        window._add_cursor_above
    )

    registry.register(
        ActionSpec("selection.add_cursor_below", "Add Cursor Below", ActionCategory.SELECTION, "Shift+Alt+DownArrow", enabled_when=has_editor),
        window._add_cursor_below
    )

    registry.register(
        ActionSpec("selection.add_cursors_to_line_ends", "Add Cursors to Line Ends", ActionCategory.SELECTION, "Shift+Alt+I", enabled_when=has_editor),
        window._add_cursors_to_line_ends
    )

    registry.register(
        ActionSpec("selection.add_next_occurrence", "Add Next Occurrence", ActionCategory.SELECTION, "Ctrl+D", enabled_when=has_editor),
        window._add_next_occurrence
    )

    registry.register(
        ActionSpec("selection.add_previous_occurrence", "Add Previous Occurrence", ActionCategory.SELECTION, enabled_when=has_editor),
        window._add_previous_occurrence
    )

    registry.register(
        ActionSpec("selection.select_all_occurrences", "Select All Occurrences", ActionCategory.SELECTION, "Ctrl+Shift+L", enabled_when=has_editor),
        window._select_all_occurrences
    )

    registry.register(
        ActionSpec("selection.ctrl_click_multicursor", "Switch to Ctrl+Click for Multi-Cursor", ActionCategory.SELECTION, checkable=True),
        window._toggle_ctrl_click_multicursor
    )

    registry.register(
        ActionSpec("selection.column_selection_mode", "Column Selection Mode", ActionCategory.SELECTION, checkable=True),
        window._toggle_column_selection_mode
    )

    # ========== VIEW MENU ACTIONS ==========

    registry.register(
        ActionSpec("view.command_palette", "Command Palette...", ActionCategory.VIEW, "Ctrl+Shift+P"),
        window.show_command_palette
    )

    registry.register(
        ActionSpec("view.open_view", "Open View...", ActionCategory.VIEW),
        window._open_view_picker
    )

    registry.register(
        ActionSpec("view.codemaps", "Codemaps", ActionCategory.VIEW, checkable=True),
        window._toggle_codemaps
    )

    registry.register(
        ActionSpec("view.explorer", "Explorer", ActionCategory.VIEW, "Ctrl+Shift+E", checkable=True),
        window._toggle_project
    )

    registry.register(
        ActionSpec("view.search", "Search", ActionCategory.VIEW, "Ctrl+Shift+F"),
        window._focus_search_panel
    )

    registry.register(
        ActionSpec("view.source_control", "Source Control", ActionCategory.VIEW, "Ctrl+Shift+G", checkable=True),
        window._toggle_source_control
    )

    registry.register(
        ActionSpec("view.deepwiki", "DeepWiki", ActionCategory.VIEW, checkable=True),
        window._toggle_deepwiki
    )

    registry.register(
        ActionSpec("view.run", "Run", ActionCategory.VIEW, "Ctrl+Shift+D", checkable=True),
        window._toggle_run_panel
    )

    registry.register(
        ActionSpec("view.extensions", "Extensions", ActionCategory.VIEW, "Ctrl+Shift+X"),
        window._open_extensions
    )

    registry.register(
        ActionSpec("view.testing", "Testing", ActionCategory.VIEW, checkable=True),
        window._toggle_testing_panel
    )

    registry.register(
        ActionSpec("view.problems", "Problems", ActionCategory.VIEW, "Ctrl+Shift+M", checkable=True),
        window._toggle_problems_panel
    )

    registry.register(
        ActionSpec("view.output", "Output", ActionCategory.VIEW, "Ctrl+Shift+H", checkable=True),
        window._toggle_output_panel
    )

    registry.register(
        ActionSpec("view.debug_console", "Debug Console", ActionCategory.VIEW, "Ctrl+Shift+Y", checkable=True),
        window._toggle_debug_console
    )

    registry.register(
        ActionSpec("view.terminal", "Terminal", ActionCategory.VIEW, "Ctrl+`", checkable=True),
        window._toggle_terminal
    )

    registry.register(
        ActionSpec("view.word_wrap", "Word Wrap", ActionCategory.VIEW, "Alt+Z", checkable=True),
        window._toggle_word_wrap
    )

    # ========== GO MENU ACTIONS ==========

    registry.register(
        ActionSpec("go.back", "Back", ActionCategory.GO, "Ctrl+Alt+-"),
        window._go_back
    )

    registry.register(
        ActionSpec("go.forward", "Forward", ActionCategory.GO, "Ctrl+Shift+-"),
        window._go_forward
    )

    registry.register(
        ActionSpec("go.last_edit", "Last Edit Location", ActionCategory.GO, "Ctrl+K Ctrl+Q"),
        window._go_to_last_edit
    )

    registry.register(
        ActionSpec("go.go_to_file", "Go to File...", ActionCategory.GO, "Ctrl+P"),
        window._open_file_picker
    )

    registry.register(
        ActionSpec("go.go_to_symbol_workspace", "Go to Symbol in Workspace...", ActionCategory.GO, "Ctrl+T"),
        window._go_to_symbol_workspace
    )

    registry.register(
        ActionSpec("go.go_to_symbol_editor", "Go to Symbol in Editor...", ActionCategory.GO, "Ctrl+Shift+O", enabled_when=has_editor),
        window._go_to_symbol_editor
    )

    registry.register(
        ActionSpec("go.go_to_definition", "Go to Definition", ActionCategory.GO, "F12", enabled_when=has_editor),
        window._go_to_definition
    )

    registry.register(
        ActionSpec("go.go_to_declaration", "Go to Declaration", ActionCategory.GO, enabled_when=has_editor),
        window._go_to_declaration
    )

    registry.register(
        ActionSpec("go.go_to_type_definition", "Go to Type Definition", ActionCategory.GO, enabled_when=has_editor),
        window._go_to_type_definition
    )

    registry.register(
        ActionSpec("go.go_to_implementations", "Go to Implementations", ActionCategory.GO, "Ctrl+F12", enabled_when=has_editor),
        window._go_to_implementations
    )

    registry.register(
        ActionSpec("go.go_to_references", "Go to References", ActionCategory.GO, "Shift+F12", enabled_when=has_editor),
        window._go_to_references
    )

    registry.register(
        ActionSpec("go.go_to_line", "Go to Line/Column...", ActionCategory.GO, "Ctrl+G", enabled_when=has_editor),
        window._go_to_line
    )

    registry.register(
        ActionSpec("go.go_to_bracket", "Go to Bracket", ActionCategory.GO, "Ctrl+Shift+\\", enabled_when=has_editor),
        window._go_to_bracket
    )

    registry.register(
        ActionSpec("go.next_problem", "Next Problem", ActionCategory.GO, "F8"),
        window._next_problem
    )

    registry.register(
        ActionSpec("go.previous_problem", "Previous Problem", ActionCategory.GO, "Shift+F8"),
        window._previous_problem
    )

    registry.register(
        ActionSpec("go.next_change", "Next Change", ActionCategory.GO, "Alt+F3"),
        window._next_change
    )

    registry.register(
        ActionSpec("go.previous_change", "Previous Change", ActionCategory.GO, "Shift+Alt+F3"),
        window._previous_change
    )

    # ========== RUN MENU ACTIONS ==========

    registry.register(
        ActionSpec("run.start_debugging", "Start Debugging", ActionCategory.RUN, "F5"),
        window._start_debugging
    )

    registry.register(
        ActionSpec("run.run_without_debugging", "Run Without Debugging", ActionCategory.RUN, "Ctrl+F5"),
        window._run_without_debugging
    )

    registry.register(
        ActionSpec("run.stop_debugging", "Stop Debugging", ActionCategory.RUN, "Shift+F5", enabled_when=debugger_running),
        window._stop_debugging
    )

    registry.register(
        ActionSpec("run.restart_debugging", "Restart Debugging", ActionCategory.RUN, "Ctrl+Shift+F5", enabled_when=debugger_running),
        window._restart_debugging
    )

    registry.register(
        ActionSpec("run.open_configurations", "Open Configurations", ActionCategory.RUN),
        window._open_debug_configurations
    )

    registry.register(
        ActionSpec("run.add_configuration", "Add Configuration...", ActionCategory.RUN),
        window._add_debug_configuration
    )

    registry.register(
        ActionSpec("run.step_over", "Step Over", ActionCategory.RUN, "F10", enabled_when=debugger_paused),
        window._step_over
    )

    registry.register(
        ActionSpec("run.step_into", "Step Into", ActionCategory.RUN, "F11", enabled_when=debugger_paused),
        window._step_into
    )

    registry.register(
        ActionSpec("run.step_out", "Step Out", ActionCategory.RUN, "Shift+F11", enabled_when=debugger_paused),
        window._step_out
    )

    registry.register(
        ActionSpec("run.continue", "Continue", ActionCategory.RUN, "F5", enabled_when=debugger_paused),
        window._continue_debugging
    )

    registry.register(
        ActionSpec("run.toggle_breakpoint", "Toggle Breakpoint", ActionCategory.RUN, "F9", enabled_when=has_editor),
        window._toggle_breakpoint
    )

    registry.register(
        ActionSpec("run.enable_all_breakpoints", "Enable All Breakpoints", ActionCategory.RUN),
        window._enable_all_breakpoints
    )

    registry.register(
        ActionSpec("run.disable_all_breakpoints", "Disable All Breakpoints", ActionCategory.RUN),
        window._disable_all_breakpoints
    )

    registry.register(
        ActionSpec("run.remove_all_breakpoints", "Remove All Breakpoints", ActionCategory.RUN),
        window._remove_all_breakpoints
    )

    registry.register(
        ActionSpec("run.install_debuggers", "Install Additional Debuggers...", ActionCategory.RUN),
        window._install_additional_debuggers
    )

    # ========== TERMINAL MENU ACTIONS ==========

    registry.register(
        ActionSpec("terminal.new", "New Terminal", ActionCategory.TERMINAL, "Ctrl+Shift+`"),
        window._new_terminal
    )

    registry.register(
        ActionSpec("terminal.split", "Split Terminal", ActionCategory.TERMINAL, "Ctrl+Shift+5"),
        window._split_terminal
    )

    registry.register(
        ActionSpec("terminal.new_window", "New Terminal Window", ActionCategory.TERMINAL, "Ctrl+Shift+Alt+`"),
        window._new_terminal_window
    )

    registry.register(
        ActionSpec("terminal.run_task", "Run Task...", ActionCategory.TERMINAL),
        window._run_task_command
    )

    registry.register(
        ActionSpec("terminal.run_build_task", "Run Build Task...", ActionCategory.TERMINAL, "Ctrl+Shift+B"),
        window._run_build_task
    )

    registry.register(
        ActionSpec("terminal.run_active_file", "Run Active File", ActionCategory.TERMINAL, enabled_when=has_editor),
        window._run_active_file_in_terminal
    )

    registry.register(
        ActionSpec("terminal.run_selected_text", "Run Selected Text", ActionCategory.TERMINAL, enabled_when=has_selection),
        window._run_selected_text
    )

    registry.register(
        ActionSpec("terminal.show_running_tasks", "Show Running Tasks...", ActionCategory.TERMINAL),
        window._show_running_tasks
    )

    registry.register(
        ActionSpec("terminal.restart_task", "Restart Running Task...", ActionCategory.TERMINAL),
        window._restart_running_task
    )

    registry.register(
        ActionSpec("terminal.terminate_task", "Terminate Task...", ActionCategory.TERMINAL),
        window._terminate_task
    )

    registry.register(
        ActionSpec("terminal.configure_tasks", "Configure Tasks...", ActionCategory.TERMINAL),
        window._configure_tasks
    )

    registry.register(
        ActionSpec("terminal.configure_default_build", "Configure Default Build Task...", ActionCategory.TERMINAL),
        window._configure_default_build_task
    )

    # ========== HELP MENU ACTIONS ==========

    registry.register(
        ActionSpec("help.show_all_commands", "Show All Commands", ActionCategory.HELP, "Ctrl+Shift+P"),
        window.show_command_palette
    )

    registry.register(
        ActionSpec("help.editor_playground", "Editor Playground", ActionCategory.HELP),
        window._open_editor_playground
    )

    registry.register(
        ActionSpec("help.open_walkthrough", "Open Walkthrough...", ActionCategory.HELP),
        window._open_walkthrough
    )

    registry.register(
        ActionSpec("help.view_license", "View License", ActionCategory.HELP),
        window._view_license
    )

    registry.register(
        ActionSpec("help.toggle_dev_tools", "Toggle Developer Tools", ActionCategory.HELP),
        window._toggle_developer_tools
    )

    registry.register(
        ActionSpec("help.process_explorer", "Open Process Explorer", ActionCategory.HELP),
        window._open_process_explorer
    )

    registry.register(
        ActionSpec("help.check_updates", "Check for Updates...", ActionCategory.HELP),
        window._check_for_updates_placeholder
    )

    registry.register(
        ActionSpec("help.about", "About", ActionCategory.HELP),
        window._show_about
    )
