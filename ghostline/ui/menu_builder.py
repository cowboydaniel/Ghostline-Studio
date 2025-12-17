"""Menu builder for Ghostline Studio.

This module builds all application menus according to the exact specification.
Menus, separators, ordering, and shortcuts match the VS Code-style specification.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar, QApplication

if TYPE_CHECKING:
    from ghostline.ui.main_window import MainWindow
    from ghostline.ui.actions import ActionRegistry

logger = logging.getLogger(__name__)


class MenuBuilder:
    """Builds all application menus according to specification."""

    def __init__(self, window: MainWindow, registry: ActionRegistry):
        self.window = window
        self.registry = registry
        self._menus: dict[str, QMenu] = {}

    def build_all_menus(self, menubar: QMenuBar) -> None:
        """Build all menus and add them to the menubar."""
        menubar.clear()

        self._build_file_menu(menubar)
        self._build_edit_menu(menubar)
        self._build_selection_menu(menubar)
        self._build_view_menu(menubar)
        self._build_go_menu(menubar)
        self._build_run_menu(menubar)
        self._build_terminal_menu(menubar)
        self._build_help_menu(menubar)

    def _create_action_with_chord(self, text: str, shortcut: str, callback: Callable) -> QAction:
        """Create an action with a chord shortcut displayed but not functional as chord."""
        action = QAction(text, self.window)
        # For chord shortcuts, we show the text but use only first part as shortcut
        if ' ' in shortcut:
            parts = shortcut.split(' ')
            action.setShortcut(QKeySequence(parts[0]))
            # Add the chord display to the text
            action.setText(f"{text}")
            action.setShortcut(QKeySequence(shortcut.replace(' ', ', ')))
        else:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        return action

    def _add_action(self, menu: QMenu, action_id: str) -> QAction | None:
        """Add a registered action to a menu."""
        action = self.registry.get(action_id)
        if action:
            menu.addAction(action)
        return action

    def _build_file_menu(self, menubar: QMenuBar) -> None:
        """Build the File menu exactly as specified."""
        menu = menubar.addMenu("File")
        self._menus["file"] = menu

        # New Text File                      Ctrl+N
        self._add_action(menu, "file.new_text_file")

        # New File...                        Ctrl+Alt+Super+N
        self._add_action(menu, "file.new_file")

        # New Window                         Ctrl+Shift+N
        self._add_action(menu, "file.new_window")

        # New Window with Profile >
        profile_menu = menu.addMenu("New Window with Profile")
        self._populate_profile_submenu(profile_menu)

        menu.addSeparator()

        # Open File...                       Ctrl+O
        self._add_action(menu, "file.open_file")

        # Open Folder...                     Ctrl+K Ctrl+O
        self._add_action(menu, "file.open_folder")

        # Open Workspace from File...
        self._add_action(menu, "file.open_workspace")

        # Open Recent >
        recent_menu = menu.addMenu("Open Recent")
        self._populate_recent_submenu(recent_menu)
        self.window._recent_menu = recent_menu

        menu.addSeparator()

        # Add Folder to Workspace...
        self._add_action(menu, "file.add_folder")

        # Save Workspace As...
        self._add_action(menu, "file.save_workspace_as")

        # Duplicate Workspace
        self._add_action(menu, "file.duplicate_workspace")

        menu.addSeparator()

        # Save                               Ctrl+S
        self._add_action(menu, "file.save")

        # Save As...                         Ctrl+Shift+S
        self._add_action(menu, "file.save_as")

        # Save All
        self._add_action(menu, "file.save_all")

        menu.addSeparator()

        # Share >
        share_menu = menu.addMenu("Share")
        self._populate_share_submenu(share_menu)

        menu.addSeparator()

        # Auto Save
        self._add_action(menu, "file.auto_save")

        # Preferences >
        prefs_menu = menu.addMenu("Preferences")
        self._populate_preferences_submenu(prefs_menu)

        menu.addSeparator()

        # Revert File
        self._add_action(menu, "file.revert")

        # Close Editor                       Ctrl+W
        self._add_action(menu, "file.close_editor")

        # Close Folder                       Ctrl+K F
        self._add_action(menu, "file.close_folder")

        # Close Window                       Alt+F4
        self._add_action(menu, "file.close_window")

        menu.addSeparator()

        # Exit                               Ctrl+Q
        self._add_action(menu, "file.exit")

    def _build_edit_menu(self, menubar: QMenuBar) -> None:
        """Build the Edit menu exactly as specified."""
        menu = menubar.addMenu("Edit")
        self._menus["edit"] = menu

        # Undo                               Ctrl+Z
        self._add_action(menu, "edit.undo")

        # Redo                               Ctrl+Y
        self._add_action(menu, "edit.redo")

        menu.addSeparator()

        # Cut                                Ctrl+X
        self._add_action(menu, "edit.cut")

        # Copy                               Ctrl+C
        self._add_action(menu, "edit.copy")

        # Paste                              Ctrl+V
        self._add_action(menu, "edit.paste")

        menu.addSeparator()

        # Find                               Ctrl+F
        self._add_action(menu, "edit.find")

        # Replace                            Ctrl+H
        self._add_action(menu, "edit.replace")

        menu.addSeparator()

        # Find in Files                      Ctrl+Shift+F
        self._add_action(menu, "edit.find_in_files")

        # Replace in Files                   Ctrl+Shift+H
        self._add_action(menu, "edit.replace_in_files")

        menu.addSeparator()

        # Toggle Line Comment                Ctrl+/
        self._add_action(menu, "edit.toggle_line_comment")

        # Toggle Block Comment               Ctrl+Shift+A
        self._add_action(menu, "edit.toggle_block_comment")

        menu.addSeparator()

        # Emmet: Expand Abbreviation         Tab
        self._add_action(menu, "edit.emmet_expand")

    def _build_selection_menu(self, menubar: QMenuBar) -> None:
        """Build the Selection menu exactly as specified."""
        menu = menubar.addMenu("Selection")
        self._menus["selection"] = menu

        # Select All                         Ctrl+A
        self._add_action(menu, "selection.select_all")

        # Expand Selection                   Shift+Alt+RightArrow
        self._add_action(menu, "selection.expand")

        # Shrink Selection                   Shift+Alt+LeftArrow
        self._add_action(menu, "selection.shrink")

        menu.addSeparator()

        # Copy Line Up                       Ctrl+Shift+Alt+UpArrow
        self._add_action(menu, "selection.copy_line_up")

        # Copy Line Down                     Ctrl+Shift+Alt+DownArrow
        self._add_action(menu, "selection.copy_line_down")

        # Move Line Up                       Alt+UpArrow
        self._add_action(menu, "selection.move_line_up")

        # Move Line Down                     Alt+DownArrow
        self._add_action(menu, "selection.move_line_down")

        # Duplicate Selection                Alt+Shift+DownArrow
        self._add_action(menu, "selection.duplicate")

        menu.addSeparator()

        # Add Cursor Above                   Shift+Alt+UpArrow
        self._add_action(menu, "selection.add_cursor_above")

        # Add Cursor Below                   Shift+Alt+DownArrow
        self._add_action(menu, "selection.add_cursor_below")

        # Add Cursors to Line Ends           Shift+Alt+I
        self._add_action(menu, "selection.add_cursors_to_line_ends")

        # Add Next Occurrence                Ctrl+D
        self._add_action(menu, "selection.add_next_occurrence")

        # Add Previous Occurrence
        self._add_action(menu, "selection.add_previous_occurrence")

        # Select All Occurrences             Ctrl+Shift+L
        self._add_action(menu, "selection.select_all_occurrences")

        menu.addSeparator()

        # Switch to Ctrl+Click for Multi-Cursor
        self._add_action(menu, "selection.ctrl_click_multicursor")

        # Column Selection Mode
        self._add_action(menu, "selection.column_selection_mode")

    def _build_view_menu(self, menubar: QMenuBar) -> None:
        """Build the View menu exactly as specified."""
        menu = menubar.addMenu("View")
        self._menus["view"] = menu
        self.window.view_menu = menu

        # Command Palette...                 Ctrl+Shift+P
        self._add_action(menu, "view.command_palette")

        # Open View...
        self._add_action(menu, "view.open_view")

        menu.addSeparator()

        # Appearance >
        appearance_menu = menu.addMenu("Appearance")
        self._populate_appearance_submenu(appearance_menu)

        # Editor Layout >
        layout_menu = menu.addMenu("Editor Layout")
        self._populate_editor_layout_submenu(layout_menu)

        menu.addSeparator()

        # Codemaps
        self._add_action(menu, "view.codemaps")

        # Explorer                           Ctrl+Shift+E
        self._add_action(menu, "view.explorer")

        # Search                             Ctrl+Shift+F
        self._add_action(menu, "view.search")

        # Source Control                     Ctrl+Shift+G
        self._add_action(menu, "view.source_control")

        # DeepWiki
        self._add_action(menu, "view.deepwiki")

        # Run                                Ctrl+Shift+D
        self._add_action(menu, "view.run")

        # Extensions                         Ctrl+Shift+X
        self._add_action(menu, "view.extensions")

        # Testing
        self._add_action(menu, "view.testing")

        menu.addSeparator()

        # Problems                           Ctrl+Shift+M
        self._add_action(menu, "view.problems")

        # Output                             Ctrl+Shift+H
        self._add_action(menu, "view.output")

        # Debug Console                      Ctrl+Shift+Y
        self._add_action(menu, "view.debug_console")

        # Terminal                           Ctrl+`
        self._add_action(menu, "view.terminal")

        menu.addSeparator()

        # Word Wrap                          Alt+Z
        self._add_action(menu, "view.word_wrap")

    def _build_go_menu(self, menubar: QMenuBar) -> None:
        """Build the Go menu exactly as specified."""
        menu = menubar.addMenu("Go")
        self._menus["go"] = menu

        # Back                               Ctrl+Alt+-
        self._add_action(menu, "go.back")

        # Forward                            Ctrl+Shift+-
        self._add_action(menu, "go.forward")

        # Last Edit Location                 Ctrl+K Ctrl+Q
        self._add_action(menu, "go.last_edit")

        menu.addSeparator()

        # Switch Editor >
        switch_editor_menu = menu.addMenu("Switch Editor")
        self._populate_switch_editor_submenu(switch_editor_menu)

        # Switch Group >
        switch_group_menu = menu.addMenu("Switch Group")
        self._populate_switch_group_submenu(switch_group_menu)

        menu.addSeparator()

        # Go to File...                      Ctrl+P
        self._add_action(menu, "go.go_to_file")

        # Go to Symbol in Workspace...       Ctrl+T
        self._add_action(menu, "go.go_to_symbol_workspace")

        # Go to Symbol in Editor...          Ctrl+Shift+O
        self._add_action(menu, "go.go_to_symbol_editor")

        menu.addSeparator()

        # Go to Definition                   F12
        self._add_action(menu, "go.go_to_definition")

        # Go to Declaration
        self._add_action(menu, "go.go_to_declaration")

        # Go to Type Definition
        self._add_action(menu, "go.go_to_type_definition")

        # Go to Implementations              Ctrl+F12
        self._add_action(menu, "go.go_to_implementations")

        # Go to References                   Shift+F12
        self._add_action(menu, "go.go_to_references")

        menu.addSeparator()

        # Go to Line/Column...               Ctrl+G
        self._add_action(menu, "go.go_to_line")

        # Go to Bracket                      Ctrl+Shift+\
        self._add_action(menu, "go.go_to_bracket")

        menu.addSeparator()

        # Next Problem                       F8
        self._add_action(menu, "go.next_problem")

        # Previous Problem                   Shift+F8
        self._add_action(menu, "go.previous_problem")

        menu.addSeparator()

        # Next Change                        Alt+F3
        self._add_action(menu, "go.next_change")

        # Previous Change                    Shift+Alt+F3
        self._add_action(menu, "go.previous_change")

    def _build_run_menu(self, menubar: QMenuBar) -> None:
        """Build the Run menu exactly as specified (Debug menu in screenshot)."""
        menu = menubar.addMenu("Run")
        self._menus["run"] = menu

        # Start Debugging                    F5
        self._add_action(menu, "run.start_debugging")

        # Run Without Debugging              Ctrl+F5
        self._add_action(menu, "run.run_without_debugging")

        # Stop Debugging                     Shift+F5
        self._add_action(menu, "run.stop_debugging")

        # Restart Debugging                  Ctrl+Shift+F5
        self._add_action(menu, "run.restart_debugging")

        menu.addSeparator()

        # Open Configurations
        self._add_action(menu, "run.open_configurations")

        # Add Configuration...
        self._add_action(menu, "run.add_configuration")

        menu.addSeparator()

        # Step Over                          F10
        self._add_action(menu, "run.step_over")

        # Step Into                          F11
        self._add_action(menu, "run.step_into")

        # Step Out                           Shift+F11
        self._add_action(menu, "run.step_out")

        # Continue                           F5
        self._add_action(menu, "run.continue")

        menu.addSeparator()

        # Toggle Breakpoint                  F9
        self._add_action(menu, "run.toggle_breakpoint")

        # New Breakpoint >
        breakpoint_menu = menu.addMenu("New Breakpoint")
        self._populate_breakpoint_submenu(breakpoint_menu)

        menu.addSeparator()

        # Enable All Breakpoints
        self._add_action(menu, "run.enable_all_breakpoints")

        # Disable All Breakpoints
        self._add_action(menu, "run.disable_all_breakpoints")

        # Remove All Breakpoints
        self._add_action(menu, "run.remove_all_breakpoints")

        menu.addSeparator()

        # Install Additional Debuggers...
        self._add_action(menu, "run.install_debuggers")

    def _build_terminal_menu(self, menubar: QMenuBar) -> None:
        """Build the Terminal menu exactly as specified."""
        menu = menubar.addMenu("Terminal")
        self._menus["terminal"] = menu

        # New Terminal                       Ctrl+Shift+`
        self._add_action(menu, "terminal.new")

        # Split Terminal                     Ctrl+Shift+5
        self._add_action(menu, "terminal.split")

        # New Terminal Window                Ctrl+Shift+Alt+`
        self._add_action(menu, "terminal.new_window")

        menu.addSeparator()

        # Run Task...
        self._add_action(menu, "terminal.run_task")

        # Run Build Task...                  Ctrl+Shift+B
        self._add_action(menu, "terminal.run_build_task")

        # Run Active File
        self._add_action(menu, "terminal.run_active_file")

        # Run Selected Text
        self._add_action(menu, "terminal.run_selected_text")

        menu.addSeparator()

        # Show Running Tasks...
        self._add_action(menu, "terminal.show_running_tasks")

        # Restart Running Task...
        self._add_action(menu, "terminal.restart_task")

        # Terminate Task...
        self._add_action(menu, "terminal.terminate_task")

        menu.addSeparator()

        # Configure Tasks...
        self._add_action(menu, "terminal.configure_tasks")

        # Configure Default Build Task...
        self._add_action(menu, "terminal.configure_default_build")

    def _build_help_menu(self, menubar: QMenuBar) -> None:
        """Build the Help menu exactly as specified."""
        menu = menubar.addMenu("Help")
        self._menus["help"] = menu

        # Show All Commands                  Ctrl+Shift+P
        self._add_action(menu, "help.show_all_commands")

        # Editor Playground
        self._add_action(menu, "help.editor_playground")

        # Open Walkthrough...
        self._add_action(menu, "help.open_walkthrough")

        menu.addSeparator()

        # View License
        self._add_action(menu, "help.view_license")

        menu.addSeparator()

        # Toggle Developer Tools
        self._add_action(menu, "help.toggle_dev_tools")

        # Open Process Explorer
        self._add_action(menu, "help.process_explorer")

        menu.addSeparator()

        # Check for Updates...
        self._add_action(menu, "help.check_updates")

        menu.addSeparator()

        # About
        self._add_action(menu, "help.about")

    # ========== SUBMENU POPULATION METHODS ==========

    def _populate_profile_submenu(self, menu: QMenu) -> None:
        """Populate the New Window with Profile submenu."""
        action = menu.addAction("Default Profile")
        action.triggered.connect(self.window._new_window_default_profile)

        menu.addSeparator()

        action = menu.addAction("Python Development")
        action.triggered.connect(lambda: self.window._new_window_with_profile("python"))

        action = menu.addAction("Web Development")
        action.triggered.connect(lambda: self.window._new_window_with_profile("web"))

        action = menu.addAction("Data Science")
        action.triggered.connect(lambda: self.window._new_window_with_profile("datascience"))

    def _populate_recent_submenu(self, menu: QMenu) -> None:
        """Populate the Open Recent submenu."""
        from pathlib import Path
        menu.clear()

        # Get recent items from workspace manager (contains both files and folders)
        recent_items = getattr(self.window.workspace_manager, 'recent_items', [])

        # Separate into folders and files
        recent_folders = []
        recent_files = []
        for item in recent_items:
            path = Path(item)
            if path.exists():
                if path.is_dir():
                    recent_folders.append(item)
                else:
                    recent_files.append(item)

        # Also get workspace-specific recent files
        workspace_recent_files = self.window.workspace_manager.get_recent_files()

        has_items = False

        if recent_folders:
            has_items = True
            for path in recent_folders[:5]:
                action = menu.addAction(str(path))
                action.triggered.connect(lambda checked, p=str(path): self.window.open_folder(p))

        if recent_files or workspace_recent_files:
            if recent_folders:
                menu.addSeparator()
            has_items = True
            # Combine and deduplicate
            all_files = list(dict.fromkeys(recent_files + workspace_recent_files))
            for path in all_files[:10]:
                action = menu.addAction(str(path))
                action.triggered.connect(lambda checked, p=str(path): self.window.open_file(p))

        if has_items:
            menu.addSeparator()
            clear_action = menu.addAction("Clear Recently Opened")
            clear_action.triggered.connect(self.window._clear_recent)
        else:
            no_recent = menu.addAction("(No Recent Items)")
            no_recent.setEnabled(False)

    def _populate_share_submenu(self, menu: QMenu) -> None:
        """Populate the Share submenu."""
        action = menu.addAction("Export to Gist...")
        action.triggered.connect(self.window._export_to_gist)

        action = menu.addAction("Copy Link to File")
        action.triggered.connect(self.window._copy_file_link)

    def _populate_preferences_submenu(self, menu: QMenu) -> None:
        """Populate the Preferences submenu."""
        action = menu.addAction("Settings")
        action.setShortcut(QKeySequence("Ctrl+,"))
        action.triggered.connect(self.window._open_settings)

        action = menu.addAction("Extensions")
        action.triggered.connect(self.window._open_extensions)

        menu.addSeparator()

        action = menu.addAction("Keyboard Shortcuts")
        action.setShortcut(QKeySequence("Ctrl+K, Ctrl+S"))
        action.triggered.connect(self.window._open_keyboard_shortcuts)

        menu.addSeparator()

        action = menu.addAction("Configure User Snippets")
        action.triggered.connect(self.window._open_snippets)

        menu.addSeparator()

        themes_menu = menu.addMenu("Color Theme")
        self.window._populate_theme_menu(themes_menu)

        action = menu.addAction("File Icon Theme")
        action.triggered.connect(self.window._open_icon_theme_picker)

        action = menu.addAction("Product Icon Theme")
        action.triggered.connect(self.window._open_product_icon_theme_picker)

    def _populate_appearance_submenu(self, menu: QMenu) -> None:
        """Populate the Appearance submenu."""
        action = menu.addAction("Full Screen")
        action.setShortcut(QKeySequence("F11"))
        action.setCheckable(True)
        action.triggered.connect(self.window._toggle_fullscreen)

        action = menu.addAction("Zen Mode")
        action.setShortcut(QKeySequence("Ctrl+K, Z"))
        action.setCheckable(True)
        action.triggered.connect(self.window._toggle_zen_mode)

        action = menu.addAction("Centered Layout")
        action.setCheckable(True)
        action.triggered.connect(self.window._toggle_centered_layout)

        menu.addSeparator()

        action = menu.addAction("Primary Side Bar")
        action.setShortcut(QKeySequence("Ctrl+B"))
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(self.window._toggle_primary_sidebar)

        action = menu.addAction("Secondary Side Bar")
        action.setShortcut(QKeySequence("Ctrl+Alt+B"))
        action.setCheckable(True)
        action.triggered.connect(self.window._toggle_secondary_sidebar)

        action = menu.addAction("Status Bar")
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(self.window._toggle_status_bar)

        action = menu.addAction("Activity Bar")
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(self.window._toggle_activity_bar)

        action = menu.addAction("Panel")
        action.setCheckable(True)
        action.triggered.connect(self.window._toggle_panel)

        menu.addSeparator()

        action = menu.addAction("Zoom In")
        action.setShortcut(QKeySequence("Ctrl+="))
        action.triggered.connect(self.window._zoom_in)

        action = menu.addAction("Zoom Out")
        action.setShortcut(QKeySequence("Ctrl+-"))
        action.triggered.connect(self.window._zoom_out)

        action = menu.addAction("Reset Zoom")
        action.setShortcut(QKeySequence("Ctrl+0"))
        action.triggered.connect(self.window._reset_zoom)

    def _populate_editor_layout_submenu(self, menu: QMenu) -> None:
        """Populate the Editor Layout submenu."""
        action = menu.addAction("Split Up")
        action.triggered.connect(self.window._split_editor_up)

        action = menu.addAction("Split Down")
        action.triggered.connect(self.window._split_editor_down)

        action = menu.addAction("Split Left")
        action.triggered.connect(self.window._split_editor_left)

        action = menu.addAction("Split Right")
        action.triggered.connect(self.window._split_editor_right)

        menu.addSeparator()

        action = menu.addAction("Single")
        action.triggered.connect(self.window._editor_layout_single)

        action = menu.addAction("Two Columns")
        action.triggered.connect(self.window._editor_layout_two_columns)

        action = menu.addAction("Three Columns")
        action.triggered.connect(self.window._editor_layout_three_columns)

        action = menu.addAction("Two Rows")
        action.triggered.connect(self.window._editor_layout_two_rows)

        action = menu.addAction("Three Rows")
        action.triggered.connect(self.window._editor_layout_three_rows)

        action = menu.addAction("Grid (2x2)")
        action.triggered.connect(self.window._editor_layout_grid)

    def _populate_switch_editor_submenu(self, menu: QMenu) -> None:
        """Populate the Switch Editor submenu."""
        action = menu.addAction("Next Editor")
        action.setShortcut(QKeySequence("Ctrl+Tab"))
        action.triggered.connect(self.window._next_editor)

        action = menu.addAction("Previous Editor")
        action.setShortcut(QKeySequence("Ctrl+Shift+Tab"))
        action.triggered.connect(self.window._previous_editor)

        menu.addSeparator()

        action = menu.addAction("Next Used Editor")
        action.triggered.connect(self.window._next_used_editor)

        action = menu.addAction("Previous Used Editor")
        action.triggered.connect(self.window._previous_used_editor)

        menu.addSeparator()

        action = menu.addAction("Next Editor in Group")
        action.triggered.connect(self.window._next_editor_in_group)

        action = menu.addAction("Previous Editor in Group")
        action.triggered.connect(self.window._previous_editor_in_group)

    def _populate_switch_group_submenu(self, menu: QMenu) -> None:
        """Populate the Switch Group submenu."""
        action = menu.addAction("Group 1")
        action.setShortcut(QKeySequence("Ctrl+1"))
        action.triggered.connect(lambda: self.window._focus_editor_group(0))

        action = menu.addAction("Group 2")
        action.setShortcut(QKeySequence("Ctrl+2"))
        action.triggered.connect(lambda: self.window._focus_editor_group(1))

        action = menu.addAction("Group 3")
        action.setShortcut(QKeySequence("Ctrl+3"))
        action.triggered.connect(lambda: self.window._focus_editor_group(2))

        menu.addSeparator()

        action = menu.addAction("Next Group")
        action.triggered.connect(self.window._next_editor_group)

        action = menu.addAction("Previous Group")
        action.triggered.connect(self.window._previous_editor_group)

    def _populate_breakpoint_submenu(self, menu: QMenu) -> None:
        """Populate the New Breakpoint submenu."""
        action = menu.addAction("Breakpoint")
        action.triggered.connect(self.window._new_breakpoint)

        action = menu.addAction("Conditional Breakpoint...")
        action.triggered.connect(self.window._new_conditional_breakpoint)

        action = menu.addAction("Logpoint...")
        action.triggered.connect(self.window._new_logpoint)

        action = menu.addAction("Function Breakpoint...")
        action.triggered.connect(self.window._new_function_breakpoint)

        action = menu.addAction("Data Breakpoint...")
        action.triggered.connect(self.window._new_data_breakpoint)

    def get_menu(self, name: str) -> QMenu | None:
        """Get a menu by name."""
        return self._menus.get(name)

    def refresh_recent_menu(self) -> None:
        """Refresh the recent files/folders submenu."""
        if hasattr(self.window, '_recent_menu'):
            self._populate_recent_submenu(self.window._recent_menu)
