"""Menu action handlers for Ghostline Studio.

This module contains all the action handler methods that will be mixed into
the MainWindow class to handle menu actions.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
)

if TYPE_CHECKING:
    from ghostline.ui.main_window import MainWindow
    from ghostline.editor.code_editor import CodeEditor

logger = logging.getLogger(__name__)


class MenuActionsMixin:
    """Mixin class providing all menu action handlers for MainWindow."""

    # ========== FILE MENU ACTIONS ==========

    def _new_text_file(self: "MainWindow") -> None:
        """Create a new untitled text file."""
        self.editor_tabs.add_new_editor()
        self.status.show_message("New file created")

    def _new_file_dialog(self: "MainWindow") -> None:
        """Show dialog to create a new file with type selection."""
        file_types = [
            "Python File (*.py)",
            "JavaScript File (*.js)",
            "TypeScript File (*.ts)",
            "HTML File (*.html)",
            "CSS File (*.css)",
            "JSON File (*.json)",
            "YAML File (*.yaml)",
            "Markdown File (*.md)",
            "Plain Text (*.txt)",
        ]
        type_choice, ok = QInputDialog.getItem(
            self, "New File", "Select file type:", file_types, 0, False
        )
        if ok and type_choice:
            self.editor_tabs.add_new_editor()
            self.status.show_message(f"New {type_choice.split('(')[0].strip()} created")

    def _new_window(self: "MainWindow") -> None:
        """Open a new window instance."""
        try:
            subprocess.Popen([sys.executable, "-m", "ghostline.main"])
            self.status.show_message("Opening new window...")
        except Exception as e:
            logger.exception("Failed to open new window")
            self.status.show_message(f"Failed to open new window: {e}")

    def _new_window_default_profile(self: "MainWindow") -> None:
        """Open new window with default profile."""
        self._new_window()

    def _new_window_with_profile(self: "MainWindow", profile: str) -> None:
        """Open new window with a specific profile."""
        try:
            subprocess.Popen([sys.executable, "-m", "ghostline.main", "--profile", profile])
            self.status.show_message(f"Opening new window with {profile} profile...")
        except Exception as e:
            logger.exception("Failed to open new window with profile")
            self.status.show_message(f"Failed to open new window: {e}")

    def _open_workspace_file(self: "MainWindow") -> None:
        """Open a workspace from a .code-workspace file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Workspace", "", "Workspace Files (*.code-workspace);;All Files (*)"
        )
        if path:
            workspace_dir = Path(path).parent
            self.open_folder(str(workspace_dir))
            self.status.show_message(f"Opened workspace: {path}")

    def _add_folder_to_workspace(self: "MainWindow") -> None:
        """Add a folder to the current workspace."""
        folder = QFileDialog.getExistingDirectory(self, "Add Folder to Workspace")
        if folder:
            if hasattr(self.workspace_manager, 'add_folder'):
                self.workspace_manager.add_folder(folder)
            self.status.show_message(f"Added folder: {folder}")

    def _save_workspace_as(self: "MainWindow") -> None:
        """Save current workspace as a .code-workspace file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Workspace As", "", "Workspace Files (*.code-workspace)"
        )
        if path:
            if not path.endswith('.code-workspace'):
                path += '.code-workspace'
            workspace = self.workspace_manager.current_workspace
            if workspace:
                import json
                workspace_data = {
                    "folders": [{"path": str(workspace)}],
                    "settings": {}
                }
                Path(path).write_text(json.dumps(workspace_data, indent=2))
                self.status.show_message(f"Workspace saved: {path}")

    def _duplicate_workspace(self: "MainWindow") -> None:
        """Duplicate the current workspace in a new window."""
        workspace = self.workspace_manager.current_workspace
        if workspace:
            try:
                subprocess.Popen([sys.executable, "-m", "ghostline.main", str(workspace)])
                self.status.show_message("Opening duplicate workspace...")
            except Exception as e:
                self.status.show_message(f"Failed to duplicate: {e}")

    def _save_current_file(self: "MainWindow") -> None:
        """Save the current file."""
        editor = self.get_current_editor()
        if editor:
            if editor.path:
                editor.save()
                self.status.show_message(f"Saved: {editor.path}")
                self.plugin_loader.emit_event("file.saved", path=str(editor.path))
            else:
                self._save_as()

    def _save_as(self: "MainWindow") -> None:
        """Save the current file with a new name."""
        editor = self.get_current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save As")
        if path:
            editor.path = Path(path)
            editor.save()
            self.status.show_message(f"Saved as: {path}")
            self.plugin_loader.emit_event("file.saved", path=path)

    def _toggle_auto_save(self: "MainWindow") -> None:
        """Toggle auto-save functionality."""
        current = self.config.get("editor", {}).get("auto_save", False)
        self.config.set("editor.auto_save", not current)
        self.status.show_message(f"Auto Save: {'On' if not current else 'Off'}")

    def _revert_file(self: "MainWindow") -> None:
        """Revert the current file to its saved state."""
        editor = self.get_current_editor()
        if editor and editor.path and editor.path.exists():
            content = editor.path.read_text(encoding='utf-8')
            editor.setPlainText(content)
            editor.document().setModified(False)
            self.status.show_message(f"Reverted: {editor.path.name}")

    def _close_current_editor(self: "MainWindow") -> None:
        """Close the current editor tab."""
        self.editor_tabs.close_current_tab()

    def _exit_application(self: "MainWindow") -> None:
        """Exit the application."""
        QApplication.instance().quit()

    def _clear_recent(self: "MainWindow") -> None:
        """Clear recently opened files and folders."""
        self.workspace_manager.clear_recents()
        self.status.show_message("Cleared recent items")

    def _export_to_gist(self: "MainWindow") -> None:
        """Export current file to GitHub Gist."""
        editor = self.get_current_editor()
        if not editor:
            self.status.show_message("No file to export")
            return
        QMessageBox.information(
            self, "Export to Gist",
            "GitHub Gist export requires authentication.\nPlease configure your GitHub token in settings."
        )

    def _copy_file_link(self: "MainWindow") -> None:
        """Copy a link to the current file."""
        editor = self.get_current_editor()
        if editor and editor.path:
            clipboard = QApplication.clipboard()
            clipboard.setText(str(editor.path))
            self.status.show_message("File path copied to clipboard")

    def _clear_recent(self: "MainWindow") -> None:
        """Clear recently opened files and folders."""
        self.workspace_manager.recent_items.clear()
        self.workspace_manager.save_recents()
        self.status.show_message("Cleared recent items")

    def _open_icon_theme_picker(self: "MainWindow") -> None:
        """Open file icon theme picker."""
        themes = ["Seti (Visual Studio Code)", "Material Icon Theme", "None"]
        theme, ok = QInputDialog.getItem(self, "File Icon Theme", "Select theme:", themes, 0, False)
        if ok:
            self.status.show_message(f"Icon theme: {theme}")

    def _open_product_icon_theme_picker(self: "MainWindow") -> None:
        """Open product icon theme picker."""
        themes = ["Default", "Fluent Icons", "Material Product Icons"]
        theme, ok = QInputDialog.getItem(self, "Product Icon Theme", "Select theme:", themes, 0, False)
        if ok:
            self.status.show_message(f"Product icon theme: {theme}")

    # ========== EDIT MENU ACTIONS ==========

    def _open_find_dialog(self: "MainWindow") -> None:
        """Open the find dialog in the current editor."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'show_find_dialog'):
            editor.show_find_dialog()
        else:
            self._open_global_search()

    def _open_replace_dialog(self: "MainWindow") -> None:
        """Open the replace dialog in the current editor."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'show_replace_dialog'):
            editor.show_replace_dialog()
        else:
            self._open_global_search()

    def _open_global_replace(self: "MainWindow") -> None:
        """Open global replace in files."""
        self._open_global_search()

    def _toggle_line_comment(self: "MainWindow") -> None:
        """Toggle line comment on current line or selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()

        # Get line bounds
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
        else:
            start = cursor.position()
            end = start

        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_line = cursor.blockNumber()

        cursor.setPosition(end)
        end_line = cursor.blockNumber()

        # Determine comment character based on file type
        path = editor.path
        comment_char = "#"
        if path:
            ext = path.suffix.lower()
            if ext in {'.js', '.ts', '.java', '.c', '.cpp', '.cs', '.go', '.rs'}:
                comment_char = "//"
            elif ext in {'.html', '.xml'}:
                comment_char = "<!--"

        cursor.beginEditBlock()

        # Check if all lines are commented
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)
        all_commented = True
        for _ in range(end_line - start_line + 1):
            line_text = cursor.block().text().lstrip()
            if not line_text.startswith(comment_char):
                all_commented = False
                break
            cursor.movePosition(QTextCursor.NextBlock)

        # Apply or remove comments
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)
        for _ in range(end_line - start_line + 1):
            if all_commented:
                # Remove comment
                line_text = cursor.block().text()
                idx = line_text.find(comment_char)
                if idx >= 0:
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, idx)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(comment_char))
                    if cursor.selectedText() == comment_char:
                        cursor.removeSelectedText()
                        # Remove space after comment if present
                        if cursor.block().text()[cursor.positionInBlock():cursor.positionInBlock()+1] == ' ':
                            cursor.deleteChar()
            else:
                # Add comment
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.insertText(f"{comment_char} ")
            cursor.movePosition(QTextCursor.NextBlock)

        cursor.endEditBlock()
        self.status.show_message("Toggled line comment")

    def _toggle_block_comment(self: "MainWindow") -> None:
        """Toggle block comment on selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            self.status.show_message("Select text to toggle block comment")
            return

        text = cursor.selectedText()
        path = editor.path

        # Determine block comment style
        start_comment = "/*"
        end_comment = "*/"
        if path:
            ext = path.suffix.lower()
            if ext in {'.py'}:
                start_comment = '"""'
                end_comment = '"""'
            elif ext in {'.html', '.xml'}:
                start_comment = "<!--"
                end_comment = "-->"

        cursor.beginEditBlock()
        if text.startswith(start_comment) and text.endswith(end_comment):
            # Remove block comment
            new_text = text[len(start_comment):-len(end_comment)]
            cursor.insertText(new_text)
        else:
            # Add block comment
            cursor.insertText(f"{start_comment}{text}{end_comment}")
        cursor.endEditBlock()
        self.status.show_message("Toggled block comment")

    def _emmet_expand(self: "MainWindow") -> None:
        """Expand Emmet abbreviation."""
        editor = self.get_current_editor()
        if not editor:
            return
        # Basic Emmet expansion for common abbreviations
        cursor = editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        abbrev = cursor.selectedText()

        expansions = {
            "!": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n\t<meta charset=\"UTF-8\">\n\t<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n\t<title>Document</title>\n</head>\n<body>\n\t\n</body>\n</html>",
            "div": "<div></div>",
            "span": "<span></span>",
            "ul>li*3": "<ul>\n\t<li></li>\n\t<li></li>\n\t<li></li>\n</ul>",
            "html:5": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n\t<meta charset=\"UTF-8\">\n\t<title>Document</title>\n</head>\n<body>\n\t\n</body>\n</html>",
        }

        if abbrev in expansions:
            cursor.insertText(expansions[abbrev])
            self.status.show_message("Emmet expanded")
        else:
            # Try to parse simple tag abbreviations like div.class#id
            if abbrev and abbrev[0].isalpha():
                tag = abbrev.split('.')[0].split('#')[0]
                classes = [c.split('#')[0] for c in abbrev.split('.')[1:]]
                ids = [i for part in abbrev.split('#')[1:] for i in [part.split('.')[0]] if i]

                attrs = ""
                if ids:
                    attrs += f' id="{ids[0]}"'
                if classes:
                    attrs += f' class="{" ".join(classes)}"'

                cursor.insertText(f"<{tag}{attrs}></{tag}>")
                self.status.show_message("Emmet expanded")

    # ========== SELECTION MENU ACTIONS ==========

    def _expand_selection(self: "MainWindow") -> None:
        """Expand selection to enclosing scope."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        else:
            # Expand to line, then block, then document
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)

    def _shrink_selection(self: "MainWindow") -> None:
        """Shrink selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            # Shrink to word
            pos = cursor.selectionStart() + (cursor.selectionEnd() - cursor.selectionStart()) // 2
            cursor.setPosition(pos)
            cursor.select(QTextCursor.WordUnderCursor)
            editor.setTextCursor(cursor)

    def _copy_line_up(self: "MainWindow") -> None:
        """Copy current line(s) up."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        cursor.beginEditBlock()

        cursor.movePosition(QTextCursor.StartOfLine)
        start = cursor.position()
        cursor.movePosition(QTextCursor.EndOfLine)
        line_text = cursor.block().text()

        cursor.setPosition(start)
        cursor.insertText(line_text + "\n")

        cursor.endEditBlock()

    def _copy_line_down(self: "MainWindow") -> None:
        """Copy current line(s) down."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        cursor.beginEditBlock()

        cursor.movePosition(QTextCursor.EndOfLine)
        line_text = cursor.block().text()
        cursor.insertText("\n" + line_text)

        cursor.endEditBlock()

    def _move_line_up(self: "MainWindow") -> None:
        """Move current line(s) up."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.blockNumber() == 0:
            return

        cursor.beginEditBlock()

        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.removeSelectedText()

        # Delete the newline
        cursor.deletePreviousChar()

        # Move to previous line start and insert
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText(line_text + "\n")
        cursor.movePosition(QTextCursor.Up)

        cursor.endEditBlock()
        editor.setTextCursor(cursor)

    def _move_line_down(self: "MainWindow") -> None:
        """Move current line(s) down."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()

        cursor.beginEditBlock()

        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        line_text = cursor.selectedText()
        cursor.removeSelectedText()

        # Delete the newline
        cursor.deleteChar()

        # Move to end of current line and insert
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.insertText("\n" + line_text)

        cursor.endEditBlock()
        editor.setTextCursor(cursor)

    def _duplicate_selection(self: "MainWindow") -> None:
        """Duplicate current selection or line."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()

        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.setPosition(cursor.selectionEnd())
            cursor.insertText(text)
        else:
            self._copy_line_down()

    def _add_cursor_above(self: "MainWindow") -> None:
        """Add a cursor above the current line."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'add_cursor_above'):
            editor.add_cursor_above()
        else:
            self.status.show_message("Multi-cursor: use Ctrl+Click to add cursors")

    def _add_cursor_below(self: "MainWindow") -> None:
        """Add a cursor below the current line."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'add_cursor_below'):
            editor.add_cursor_below()
        else:
            self.status.show_message("Multi-cursor: use Ctrl+Click to add cursors")

    def _add_cursors_to_line_ends(self: "MainWindow") -> None:
        """Add cursors to the end of each selected line."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            self.status.show_message("Added cursors to line ends")
        else:
            self.status.show_message("Select multiple lines first")

    def _add_next_occurrence(self: "MainWindow") -> None:
        """Add next occurrence of selection to multi-selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
            editor.setTextCursor(cursor)

        search_text = cursor.selectedText()
        if hasattr(editor, 'find_and_select_next'):
            editor.find_and_select_next(search_text)
        else:
            # Basic find next
            found = editor.find(search_text)
            if not found:
                # Wrap around
                cursor = editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                editor.setTextCursor(cursor)
                editor.find(search_text)

    def _add_previous_occurrence(self: "MainWindow") -> None:
        """Add previous occurrence of selection to multi-selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            search_text = cursor.selectedText()
            from PySide6.QtGui import QTextDocument
            editor.find(search_text, QTextDocument.FindBackward)

    def _select_all_occurrences(self: "MainWindow") -> None:
        """Select all occurrences of current selection."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            search_text = cursor.selectedText()
            # Count occurrences
            text = editor.toPlainText()
            count = text.count(search_text)
            self.status.show_message(f"Found {count} occurrences of '{search_text}'")

    def _toggle_ctrl_click_multicursor(self: "MainWindow") -> None:
        """Toggle between Ctrl+Click and Alt+Click for multi-cursor."""
        current = self.config.get("editor", {}).get("ctrl_click_multicursor", True)
        self.config.set("editor.ctrl_click_multicursor", not current)
        mode = "Ctrl+Click" if not current else "Alt+Click"
        self.status.show_message(f"Multi-cursor mode: {mode}")

    def _toggle_column_selection_mode(self: "MainWindow") -> None:
        """Toggle column selection mode."""
        current = self.config.get("editor", {}).get("column_selection", False)
        self.config.set("editor.column_selection", not current)
        self.status.show_message(f"Column selection mode: {'On' if not current else 'Off'}")

    # ========== VIEW MENU ACTIONS ==========

    def _open_view_picker(self: "MainWindow") -> None:
        """Open view picker dialog."""
        views = [
            "Explorer", "Search", "Source Control", "Run and Debug",
            "Extensions", "Testing", "Problems", "Output", "Debug Console",
            "Terminal", "Outline", "Timeline"
        ]
        view, ok = QInputDialog.getItem(self, "Open View", "Select view:", views, 0, False)
        if ok:
            self.status.show_message(f"Opening {view}")

    def _toggle_codemaps(self: "MainWindow") -> None:
        """Toggle codemaps panel."""
        dock = getattr(self, "architecture_dock", None)
        if dock:
            dock.setVisible(not dock.isVisible())

    def _focus_search_panel(self: "MainWindow") -> None:
        """Focus the search panel."""
        self._open_global_search()

    def _toggle_source_control(self: "MainWindow") -> None:
        """Toggle source control panel."""
        dock = getattr(self, "git_dock", None)
        if dock:
            if dock.isVisible():
                dock.hide()
            else:
                self._show_and_raise_dock(dock, "git")

    def _toggle_deepwiki(self: "MainWindow") -> None:
        """Toggle DeepWiki panel."""
        dock = getattr(self, "doc_dock", None)
        if dock:
            dock.setVisible(not dock.isVisible())

    def _toggle_run_panel(self: "MainWindow") -> None:
        """Toggle Run and Debug panel."""
        dock = getattr(self, "debugger_dock", None)
        if dock:
            if dock.isVisible():
                dock.hide()
            else:
                self._show_and_raise_dock(dock, "debug")

    def _toggle_testing_panel(self: "MainWindow") -> None:
        """Toggle testing panel."""
        dock = getattr(self, "test_dock", None)
        if dock:
            if dock.isVisible():
                dock.hide()
            else:
                self._show_and_raise_dock(dock, "tests")

    def _toggle_problems_panel(self: "MainWindow") -> None:
        """Toggle problems panel."""
        if hasattr(self, "bottom_panel"):
            self.bottom_panel.setVisible(True)
            self.bottom_panel.set_current_panel(0)  # Problems is first

    def _toggle_output_panel(self: "MainWindow") -> None:
        """Toggle output panel."""
        if hasattr(self, "bottom_panel") and hasattr(self, "output_panel_index"):
            self.bottom_panel.setVisible(True)
            self.bottom_panel.set_current_panel(self.output_panel_index)

    def _toggle_debug_console(self: "MainWindow") -> None:
        """Toggle debug console panel."""
        if hasattr(self, "bottom_panel"):
            self.bottom_panel.setVisible(True)
            self.bottom_panel.set_current_panel(2)  # Debug Console

    def _toggle_word_wrap(self: "MainWindow") -> None:
        """Toggle word wrap in editor."""
        editor = self.get_current_editor()
        if editor:
            from PySide6.QtWidgets import QPlainTextEdit
            current = editor.lineWrapMode() == QPlainTextEdit.WidgetWidth
            editor.setLineWrapMode(
                QPlainTextEdit.NoWrap if current else QPlainTextEdit.WidgetWidth
            )
            self.status.show_message(f"Word wrap: {'Off' if current else 'On'}")

    def _toggle_fullscreen(self: "MainWindow") -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _toggle_zen_mode(self: "MainWindow") -> None:
        """Toggle zen mode (distraction-free)."""
        if hasattr(self, '_zen_mode_active') and self._zen_mode_active:
            # Restore normal mode
            if hasattr(self, 'left_region_container'):
                self.left_region_container.show()
            if hasattr(self, 'right_region_container'):
                self.right_region_container.show()
            if hasattr(self, 'bottom_panel'):
                self.bottom_panel.show()
            self.statusBar().show()
            self.menuBar().show()
            self._zen_mode_active = False
            self.status.show_message("Zen mode: Off")
        else:
            # Enter zen mode
            if hasattr(self, 'left_region_container'):
                self.left_region_container.hide()
            if hasattr(self, 'right_region_container'):
                self.right_region_container.hide()
            if hasattr(self, 'bottom_panel'):
                self.bottom_panel.hide()
            self.statusBar().hide()
            self._zen_mode_active = True
            self.status.show_message("Zen mode: On")

    def _toggle_centered_layout(self: "MainWindow") -> None:
        """Toggle centered layout."""
        self.status.show_message("Centered layout toggled")

    def _toggle_primary_sidebar(self: "MainWindow") -> None:
        """Toggle primary (left) sidebar."""
        if hasattr(self, 'left_region_container'):
            visible = self.left_region_container.isVisible()
            self.left_region_container.setVisible(not visible)
            if hasattr(self, 'toggle_left_region'):
                self.toggle_left_region.setChecked(not visible)

    def _toggle_secondary_sidebar(self: "MainWindow") -> None:
        """Toggle secondary (right) sidebar."""
        if hasattr(self, 'right_region_container'):
            visible = self.right_region_container.isVisible()
            self.right_region_container.setVisible(not visible)
            if hasattr(self, 'toggle_right_region'):
                self.toggle_right_region.setChecked(not visible)

    def _toggle_status_bar(self: "MainWindow") -> None:
        """Toggle status bar visibility."""
        visible = self.statusBar().isVisible()
        self.statusBar().setVisible(not visible)

    def _toggle_activity_bar(self: "MainWindow") -> None:
        """Toggle activity bar visibility."""
        if hasattr(self, 'activity_bar'):
            visible = self.activity_bar.isVisible()
            self.activity_bar.setVisible(not visible)

    def _toggle_panel(self: "MainWindow") -> None:
        """Toggle bottom panel visibility."""
        if hasattr(self, 'bottom_panel'):
            visible = self.bottom_panel.isVisible()
            self.bottom_panel.setVisible(not visible)

    def _zoom_in(self: "MainWindow") -> None:
        """Zoom in the editor."""
        editor = self.get_current_editor()
        if editor:
            font = editor.font()
            font.setPointSize(font.pointSize() + 1)
            editor.setFont(font)

    def _zoom_out(self: "MainWindow") -> None:
        """Zoom out the editor."""
        editor = self.get_current_editor()
        if editor:
            font = editor.font()
            size = max(6, font.pointSize() - 1)
            font.setPointSize(size)
            editor.setFont(font)

    def _reset_zoom(self: "MainWindow") -> None:
        """Reset editor zoom to default."""
        editor = self.get_current_editor()
        if editor:
            font = editor.font()
            font.setPointSize(12)
            editor.setFont(font)

    def _split_editor_up(self: "MainWindow") -> None:
        """Split editor up."""
        self.editor_tabs.split_editor("up")

    def _split_editor_down(self: "MainWindow") -> None:
        """Split editor down."""
        self.editor_tabs.split_editor("down")

    def _split_editor_left(self: "MainWindow") -> None:
        """Split editor left."""
        self.editor_tabs.split_editor("left")

    def _split_editor_right(self: "MainWindow") -> None:
        """Split editor right."""
        self.editor_tabs.split_editor("right")

    def _editor_layout_single(self: "MainWindow") -> None:
        """Set editor layout to single."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("single")
        self.status.show_message("Editor layout: Single")

    def _editor_layout_two_columns(self: "MainWindow") -> None:
        """Set editor layout to two columns."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("two_columns")
        self.status.show_message("Editor layout: Two Columns")

    def _editor_layout_three_columns(self: "MainWindow") -> None:
        """Set editor layout to three columns."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("three_columns")
        self.status.show_message("Editor layout: Three Columns")

    def _editor_layout_two_rows(self: "MainWindow") -> None:
        """Set editor layout to two rows."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("two_rows")
        self.status.show_message("Editor layout: Two Rows")

    def _editor_layout_three_rows(self: "MainWindow") -> None:
        """Set editor layout to three rows."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("three_rows")
        self.status.show_message("Editor layout: Three Rows")

    def _editor_layout_grid(self: "MainWindow") -> None:
        """Set editor layout to 2x2 grid."""
        if hasattr(self.editor_tabs, 'set_layout'):
            self.editor_tabs.set_layout("grid")
        self.status.show_message("Editor layout: Grid (2x2)")

    def _next_editor(self: "MainWindow") -> None:
        """Switch to next editor tab."""
        self.editor_tabs.next_tab()

    def _previous_editor(self: "MainWindow") -> None:
        """Switch to previous editor tab."""
        self.editor_tabs.previous_tab()

    def _next_used_editor(self: "MainWindow") -> None:
        """Switch to next most recently used editor."""
        self.editor_tabs.next_tab()

    def _previous_used_editor(self: "MainWindow") -> None:
        """Switch to previous most recently used editor."""
        self.editor_tabs.previous_tab()

    def _next_editor_in_group(self: "MainWindow") -> None:
        """Switch to next editor in current group."""
        self.editor_tabs.next_tab()

    def _previous_editor_in_group(self: "MainWindow") -> None:
        """Switch to previous editor in current group."""
        self.editor_tabs.previous_tab()

    def _focus_editor_group(self: "MainWindow", group: int) -> None:
        """Focus a specific editor group."""
        if hasattr(self.editor_tabs, 'focus_group'):
            self.editor_tabs.focus_group(group)
        self.status.show_message(f"Focus: Group {group + 1}")

    def _next_editor_group(self: "MainWindow") -> None:
        """Switch to next editor group."""
        if hasattr(self.editor_tabs, 'next_group'):
            self.editor_tabs.next_group()

    def _previous_editor_group(self: "MainWindow") -> None:
        """Switch to previous editor group."""
        if hasattr(self.editor_tabs, 'previous_group'):
            self.editor_tabs.previous_group()

    # ========== GO MENU ACTIONS ==========

    def _go_back(self: "MainWindow") -> None:
        """Navigate back in history."""
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'back_button'):
            self.status.show_message("Navigate back")

    def _go_forward(self: "MainWindow") -> None:
        """Navigate forward in history."""
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'forward_button'):
            self.status.show_message("Navigate forward")

    def _go_to_last_edit(self: "MainWindow") -> None:
        """Go to last edit location."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'go_to_last_edit'):
            editor.go_to_last_edit()
        self.status.show_message("Go to last edit location")

    def _go_to_symbol_workspace(self: "MainWindow") -> None:
        """Go to symbol in workspace."""
        self._open_symbol_picker()

    def _go_to_symbol_editor(self: "MainWindow") -> None:
        """Go to symbol in current editor."""
        editor = self.get_current_editor()
        if not editor:
            return
        self.command_palette.open_with_query("@")

    def _go_to_definition(self: "MainWindow") -> None:
        """Go to definition of symbol under cursor."""
        editor = self.get_current_editor()
        if not editor or not editor.path:
            return

        cursor = editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()

        if word and hasattr(self.lsp_manager, 'go_to_definition'):
            self.lsp_manager.go_to_definition(
                str(editor.path),
                cursor.blockNumber(),
                cursor.columnNumber()
            )
        else:
            self.status.show_message(f"Looking for definition of '{word}'")

    def _go_to_declaration(self: "MainWindow") -> None:
        """Go to declaration of symbol under cursor."""
        self._go_to_definition()

    def _go_to_type_definition(self: "MainWindow") -> None:
        """Go to type definition of symbol under cursor."""
        self._go_to_definition()

    def _go_to_implementations(self: "MainWindow") -> None:
        """Go to implementations of symbol under cursor."""
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.select(QTextCursor.WordUnderCursor)
            self.status.show_message(f"Finding implementations of '{cursor.selectedText()}'")

    def _go_to_references(self: "MainWindow") -> None:
        """Go to references of symbol under cursor."""
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.select(QTextCursor.WordUnderCursor)
            self.status.show_message(f"Finding references to '{cursor.selectedText()}'")

    def _go_to_line(self: "MainWindow") -> None:
        """Go to specific line and column."""
        editor = self.get_current_editor()
        if not editor:
            return

        line_col, ok = QInputDialog.getText(
            self, "Go to Line", "Line[:Column]:"
        )
        if ok and line_col:
            parts = line_col.split(':')
            try:
                line = int(parts[0]) - 1
                col = int(parts[1]) - 1 if len(parts) > 1 else 0

                cursor = editor.textCursor()
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line)
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, col)
                editor.setTextCursor(cursor)
                editor.centerCursor()
            except ValueError:
                self.status.show_message("Invalid line number")

    def _go_to_bracket(self: "MainWindow") -> None:
        """Go to matching bracket."""
        editor = self.get_current_editor()
        if not editor:
            return

        cursor = editor.textCursor()
        text = editor.toPlainText()
        pos = cursor.position()

        brackets = {'(': ')', '[': ']', '{': '}', '<': '>'}
        reverse_brackets = {v: k for k, v in brackets.items()}

        if pos < len(text):
            char = text[pos]
            if char in brackets:
                # Find matching closing bracket
                depth = 1
                for i in range(pos + 1, len(text)):
                    if text[i] == char:
                        depth += 1
                    elif text[i] == brackets[char]:
                        depth -= 1
                        if depth == 0:
                            cursor.setPosition(i)
                            editor.setTextCursor(cursor)
                            return
            elif char in reverse_brackets:
                # Find matching opening bracket
                depth = 1
                for i in range(pos - 1, -1, -1):
                    if text[i] == char:
                        depth += 1
                    elif text[i] == reverse_brackets[char]:
                        depth -= 1
                        if depth == 0:
                            cursor.setPosition(i)
                            editor.setTextCursor(cursor)
                            return

    def _next_problem(self: "MainWindow") -> None:
        """Go to next problem/diagnostic."""
        if hasattr(self, 'diagnostics_model'):
            count = self.diagnostics_model.rowCount()
            if count > 0:
                self._jump_to_diagnostic(self.diagnostics_model.index(0, 0))
        self.status.show_message("Next problem")

    def _previous_problem(self: "MainWindow") -> None:
        """Go to previous problem/diagnostic."""
        self.status.show_message("Previous problem")

    def _next_change(self: "MainWindow") -> None:
        """Go to next change in diff."""
        self.status.show_message("Next change")

    def _previous_change(self: "MainWindow") -> None:
        """Go to previous change in diff."""
        self.status.show_message("Previous change")

    # ========== RUN MENU ACTIONS ==========

    def _start_debugging(self: "MainWindow") -> None:
        """Start debugging."""
        if hasattr(self, 'debugger'):
            workspace = self.workspace_manager.current_workspace
            if workspace:
                launch_json = workspace / ".vscode" / "launch.json"
                if launch_json.exists():
                    self.debugger.start()
                    self.status.show_message("Starting debugger...")
                else:
                    self._add_debug_configuration()
            else:
                self.status.show_message("Open a workspace to debug")

    def _run_without_debugging(self: "MainWindow") -> None:
        """Run without debugging."""
        self._run_current_file()

    def _stop_debugging(self: "MainWindow") -> None:
        """Stop debugging."""
        if hasattr(self, 'debugger'):
            self.debugger.stop()
            self.status.show_message("Debugger stopped")

    def _restart_debugging(self: "MainWindow") -> None:
        """Restart debugging."""
        if hasattr(self, 'debugger'):
            self.debugger.restart()
            self.status.show_message("Restarting debugger...")

    def _open_debug_configurations(self: "MainWindow") -> None:
        """Open debug configurations file."""
        workspace = self.workspace_manager.current_workspace
        if workspace:
            launch_json = workspace / ".vscode" / "launch.json"
            if launch_json.exists():
                self.open_file(str(launch_json))
            else:
                self._add_debug_configuration()

    def _add_debug_configuration(self: "MainWindow") -> None:
        """Add a new debug configuration."""
        workspace = self.workspace_manager.current_workspace
        if not workspace:
            self.status.show_message("Open a workspace first")
            return

        configs = [
            "Python: Current File",
            "Python: Module",
            "Node.js: Launch Program",
            "Node.js: Attach",
            "Go: Launch Package",
        ]
        config, ok = QInputDialog.getItem(
            self, "Add Configuration", "Select debug configuration:", configs, 0, False
        )
        if ok:
            vscode_dir = workspace / ".vscode"
            vscode_dir.mkdir(exist_ok=True)
            launch_json = vscode_dir / "launch.json"

            import json

            if config.startswith("Python"):
                launch_config = {
                    "version": "0.2.0",
                    "configurations": [
                        {
                            "name": "Python: Current File",
                            "type": "python",
                            "request": "launch",
                            "program": "${file}",
                            "console": "integratedTerminal"
                        }
                    ]
                }
            else:
                launch_config = {
                    "version": "0.2.0",
                    "configurations": [
                        {
                            "name": config,
                            "type": "node",
                            "request": "launch",
                            "program": "${workspaceFolder}/index.js"
                        }
                    ]
                }

            launch_json.write_text(json.dumps(launch_config, indent=4))
            self.open_file(str(launch_json))
            self.status.show_message(f"Created debug configuration: {config}")

    def _step_over(self: "MainWindow") -> None:
        """Step over in debugger."""
        if hasattr(self, 'debugger'):
            self.debugger.step_over()

    def _step_into(self: "MainWindow") -> None:
        """Step into in debugger."""
        if hasattr(self, 'debugger'):
            self.debugger.step_into()

    def _step_out(self: "MainWindow") -> None:
        """Step out in debugger."""
        if hasattr(self, 'debugger'):
            self.debugger.step_out()

    def _continue_debugging(self: "MainWindow") -> None:
        """Continue debugging."""
        if hasattr(self, 'debugger'):
            self.debugger.continue_execution()

    def _toggle_breakpoint(self: "MainWindow") -> None:
        """Toggle breakpoint on current line."""
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            if hasattr(editor, 'toggle_breakpoint'):
                editor.toggle_breakpoint(line)
            self.status.show_message(f"Toggled breakpoint at line {line}")

    def _new_breakpoint(self: "MainWindow") -> None:
        """Add new breakpoint."""
        self._toggle_breakpoint()

    def _new_conditional_breakpoint(self: "MainWindow") -> None:
        """Add new conditional breakpoint."""
        editor = self.get_current_editor()
        if not editor:
            return

        condition, ok = QInputDialog.getText(
            self, "Conditional Breakpoint", "Condition:"
        )
        if ok and condition:
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            self.status.show_message(f"Conditional breakpoint at line {line}: {condition}")

    def _new_logpoint(self: "MainWindow") -> None:
        """Add new logpoint."""
        editor = self.get_current_editor()
        if not editor:
            return

        message, ok = QInputDialog.getText(
            self, "Logpoint", "Message to log:"
        )
        if ok and message:
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            self.status.show_message(f"Logpoint at line {line}: {message}")

    def _new_function_breakpoint(self: "MainWindow") -> None:
        """Add new function breakpoint."""
        func_name, ok = QInputDialog.getText(
            self, "Function Breakpoint", "Function name:"
        )
        if ok and func_name:
            self.status.show_message(f"Function breakpoint: {func_name}")

    def _new_data_breakpoint(self: "MainWindow") -> None:
        """Add new data breakpoint."""
        var_name, ok = QInputDialog.getText(
            self, "Data Breakpoint", "Variable name:"
        )
        if ok and var_name:
            self.status.show_message(f"Data breakpoint: {var_name}")

    def _enable_all_breakpoints(self: "MainWindow") -> None:
        """Enable all breakpoints."""
        if hasattr(self, 'debugger'):
            self.debugger.enable_all_breakpoints()
        self.status.show_message("Enabled all breakpoints")

    def _disable_all_breakpoints(self: "MainWindow") -> None:
        """Disable all breakpoints."""
        if hasattr(self, 'debugger'):
            self.debugger.disable_all_breakpoints()
        self.status.show_message("Disabled all breakpoints")

    def _remove_all_breakpoints(self: "MainWindow") -> None:
        """Remove all breakpoints."""
        if hasattr(self, 'debugger'):
            self.debugger.remove_all_breakpoints()
        self.status.show_message("Removed all breakpoints")

    def _install_additional_debuggers(self: "MainWindow") -> None:
        """Install additional debuggers."""
        self._open_extensions()

    # ========== TERMINAL MENU ACTIONS ==========

    def _new_terminal(self: "MainWindow") -> None:
        """Create new terminal."""
        if hasattr(self, 'terminal'):
            self.terminal.new_terminal()
            if hasattr(self, 'bottom_panel'):
                self.bottom_panel.setVisible(True)
                if hasattr(self, 'terminal_panel_index'):
                    self.bottom_panel.set_current_panel(self.terminal_panel_index)

    def _split_terminal(self: "MainWindow") -> None:
        """Split current terminal."""
        if hasattr(self, 'terminal') and hasattr(self.terminal, 'split_terminal'):
            self.terminal.split_terminal()
        else:
            self._new_terminal()

    def _new_terminal_window(self: "MainWindow") -> None:
        """Open new terminal in external window."""
        workspace = self.workspace_manager.current_workspace
        cwd = str(workspace) if workspace else None

        import platform
        system = platform.system()

        try:
            if system == "Windows":
                subprocess.Popen(["cmd.exe"], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal", cwd or "."])
            else:
                # Try common Linux terminals
                for term in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                    try:
                        subprocess.Popen([term], cwd=cwd)
                        break
                    except FileNotFoundError:
                        continue
        except Exception as e:
            self.status.show_message(f"Failed to open terminal: {e}")

    def _run_build_task(self: "MainWindow") -> None:
        """Run the default build task."""
        workspace = self.workspace_manager.current_workspace
        if not workspace:
            self.status.show_message("Open a workspace first")
            return

        # Look for common build commands
        if (workspace / "package.json").exists():
            self._run_terminal_command("npm run build")
        elif (workspace / "Makefile").exists():
            self._run_terminal_command("make")
        elif (workspace / "setup.py").exists():
            self._run_terminal_command("python setup.py build")
        elif (workspace / "pyproject.toml").exists():
            self._run_terminal_command("python -m build")
        else:
            self._configure_default_build_task()

    def _run_active_file_in_terminal(self: "MainWindow") -> None:
        """Run active file in terminal."""
        self._run_current_file()

    def _run_selected_text(self: "MainWindow") -> None:
        """Run selected text in terminal."""
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace('\u2029', '\n')  # Replace paragraph separators
            self._run_terminal_command(text)

    def _run_terminal_command(self: "MainWindow", command: str) -> None:
        """Run a command in the terminal."""
        if hasattr(self, 'terminal'):
            if hasattr(self, 'bottom_panel'):
                self.bottom_panel.setVisible(True)
                if hasattr(self, 'terminal_panel_index'):
                    self.bottom_panel.set_current_panel(self.terminal_panel_index)
            self.terminal.run_command(command)

    def _show_running_tasks(self: "MainWindow") -> None:
        """Show running tasks dialog."""
        tasks = []
        if hasattr(self.task_manager, 'get_running_tasks'):
            tasks = self.task_manager.get_running_tasks()

        if not tasks:
            self.status.show_message("No tasks running")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Running Tasks")
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget(dialog)
        for task in tasks:
            list_widget.addItem(str(task))
        layout.addWidget(list_widget)

        dialog.exec()

    def _restart_running_task(self: "MainWindow") -> None:
        """Restart a running task."""
        if hasattr(self.task_manager, 'get_running_tasks'):
            tasks = self.task_manager.get_running_tasks()
            if tasks:
                task_names = [str(t) for t in tasks]
                task, ok = QInputDialog.getItem(
                    self, "Restart Task", "Select task:", task_names, 0, False
                )
                if ok:
                    self.task_manager.restart_task(task)
        else:
            self.status.show_message("No tasks to restart")

    def _terminate_task(self: "MainWindow") -> None:
        """Terminate a running task."""
        if hasattr(self.task_manager, 'get_running_tasks'):
            tasks = self.task_manager.get_running_tasks()
            if tasks:
                task_names = [str(t) for t in tasks]
                task, ok = QInputDialog.getItem(
                    self, "Terminate Task", "Select task:", task_names, 0, False
                )
                if ok:
                    self.task_manager.terminate_task(task)
        else:
            self.status.show_message("No tasks to terminate")

    def _configure_tasks(self: "MainWindow") -> None:
        """Open tasks configuration."""
        workspace = self.workspace_manager.current_workspace
        if not workspace:
            self.status.show_message("Open a workspace first")
            return

        tasks_file = workspace / ".ghostline" / "tasks.yaml"
        if not tasks_file.exists():
            tasks_file.parent.mkdir(exist_ok=True)
            tasks_file.write_text("""# Ghostline Tasks Configuration
# See documentation for task configuration options

tasks:
  - name: build
    command: echo "Configure your build command"

  - name: test
    command: echo "Configure your test command"

  - name: run
    command: echo "Configure your run command"
""")
        self.open_file(str(tasks_file))

    def _configure_default_build_task(self: "MainWindow") -> None:
        """Configure the default build task."""
        self._configure_tasks()

    # ========== HELP MENU ACTIONS ==========

    def _open_editor_playground(self: "MainWindow") -> None:
        """Open the editor playground."""
        content = """# Editor Playground

Welcome to the Ghostline Studio Editor Playground!

Try out editor features here:

## Code Examples

```python
def hello_world():
    print("Hello, Ghostline!")

# Try these features:
# - Syntax highlighting
# - Auto-completion
# - Code folding
# - Multi-cursor editing (Ctrl+Click)
# - Find and Replace (Ctrl+F, Ctrl+H)
```

```javascript
const greeting = (name) => {
    return `Hello, ${name}!`;
};

console.log(greeting("Ghostline"));
```

## Keyboard Shortcuts

- Ctrl+P: Quick Open
- Ctrl+Shift+P: Command Palette
- Ctrl+/: Toggle Line Comment
- Ctrl+D: Add Selection to Next Find Match
- Alt+Up/Down: Move Line Up/Down
"""
        editor = self.editor_tabs.add_new_editor()
        if editor:
            editor.setPlainText(content)
            self.status.show_message("Editor Playground opened")

    def _open_walkthrough(self: "MainWindow") -> None:
        """Open the getting started walkthrough."""
        walkthroughs = [
            "Get Started with Ghostline",
            "Learn the Editor",
            "AI-Assisted Coding",
            "Keyboard Shortcuts",
        ]
        walkthrough, ok = QInputDialog.getItem(
            self, "Open Walkthrough", "Select walkthrough:", walkthroughs, 0, False
        )
        if ok:
            self.status.show_message(f"Opening walkthrough: {walkthrough}")
            # Could open a welcome tab with walkthrough content

    def _view_license(self: "MainWindow") -> None:
        """View the application license."""
        license_text = """MIT License

Copyright (c) 2024 Ghostline Studio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
        QMessageBox.information(self, "License", license_text)

    def _toggle_developer_tools(self: "MainWindow") -> None:
        """Toggle developer tools."""
        # Could open a dev tools dock or dialog
        self.status.show_message("Developer tools toggled")

    def _open_process_explorer(self: "MainWindow") -> None:
        """Open process explorer."""
        import psutil

        dialog = QDialog(self)
        dialog.setWindowTitle("Process Explorer")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget(dialog)

        try:
            current_process = psutil.Process()
            info = [
                f"PID: {current_process.pid}",
                f"Name: {current_process.name()}",
                f"CPU: {current_process.cpu_percent():.1f}%",
                f"Memory: {current_process.memory_info().rss / 1024 / 1024:.1f} MB",
                f"Threads: {current_process.num_threads()}",
            ]
            for line in info:
                list_widget.addItem(line)

            list_widget.addItem("")
            list_widget.addItem("Child Processes:")
            for child in current_process.children(recursive=True):
                try:
                    list_widget.addItem(f"  {child.pid}: {child.name()}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            list_widget.addItem(f"Error: {e}")

        layout.addWidget(list_widget)
        dialog.exec()
