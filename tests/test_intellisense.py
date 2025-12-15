"""Test IntelliSense auto-trigger and snippet functionality."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from ghostline.editor.code_editor import CodeEditor, SnippetManager, CompletionWidget
from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager


class TestSnippetManager:
    """Test snippet parsing and insertion."""

    def test_parse_simple_snippet(self, qt_app):
        """Test parsing a simple snippet with placeholders."""
        editor = CodeEditor()
        snippet_manager = SnippetManager(editor)

        snippet_text = "def ${1:function_name}(${2:args}):\n    ${3:pass}"
        parsed_text, tab_stops = snippet_manager.parse_snippet(snippet_text)

        assert "def function_name(args):" in parsed_text
        assert "pass" in parsed_text
        assert len(tab_stops) == 3
        assert tab_stops[0][2] == "function_name"  # placeholder text
        assert tab_stops[1][2] == "args"
        assert tab_stops[2][2] == "pass"

    def test_parse_snippet_with_simple_tabstops(self, qt_app):
        """Test parsing snippets with simple $1 style tab stops."""
        editor = CodeEditor()
        snippet_manager = SnippetManager(editor)

        snippet_text = "for $1 in $2:\n    $0"
        parsed_text, tab_stops = snippet_manager.parse_snippet(snippet_text)

        assert parsed_text == "for  in :\n    "
        assert len(tab_stops) == 3

    def test_parse_snippet_with_choices(self, qt_app):
        """Test parsing snippets with choice placeholders."""
        editor = CodeEditor()
        snippet_manager = SnippetManager(editor)

        snippet_text = "${1|public,private,protected|} class ${2:MyClass}"
        parsed_text, tab_stops = snippet_manager.parse_snippet(snippet_text)

        assert "public class MyClass" in parsed_text
        assert len(tab_stops) == 2

    def test_insert_snippet(self, qt_app):
        """Test inserting a snippet into the editor."""
        editor = CodeEditor()
        snippet_manager = SnippetManager(editor)

        editor.setPlainText("")
        snippet_manager.insert_snippet("def ${1:func}():\n    ${2:pass}")

        text = editor.toPlainText()
        assert "def func():" in text
        assert "pass" in text
        assert snippet_manager.active_snippet is not None

    def test_tab_stop_navigation(self, qt_app):
        """Test navigating through tab stops."""
        editor = CodeEditor()
        snippet_manager = SnippetManager(editor)

        editor.setPlainText("")
        snippet_manager.insert_snippet("${1:first} ${2:second} ${3:third}")

        # First tab stop should be selected
        cursor = editor.textCursor()
        assert cursor.selectedText() == "first"

        # Jump to next tab stop
        result = snippet_manager.jump_to_next_tab_stop()
        assert result is True
        cursor = editor.textCursor()
        assert cursor.selectedText() == "second"

        # Jump to next tab stop
        result = snippet_manager.jump_to_next_tab_stop()
        assert result is True
        cursor = editor.textCursor()
        assert cursor.selectedText() == "third"

        # No more tab stops
        result = snippet_manager.jump_to_next_tab_stop()
        assert result is False
        assert snippet_manager.active_snippet is None


class TestCompletionWidget:
    """Test completion widget functionality."""

    def test_completion_widget_creation(self, qt_app):
        """Test creating a completion widget."""
        editor = CodeEditor()
        widget = CompletionWidget(editor)

        assert widget is not None
        assert widget.editor == editor
        assert widget.isHidden()

    def test_show_completions(self, qt_app):
        """Test showing completions with filtering."""
        editor = CodeEditor()
        widget = CompletionWidget(editor)

        items = [
            {"label": "print", "kind": 3, "detail": "Built-in function"},
            {"label": "printf", "kind": 3, "detail": "Format and print"},
            {"label": "parse", "kind": 3, "detail": "Parse data"},
            {"label": "path", "kind": 6, "detail": "Path object"},
        ]

        widget.show_completions(items, "pr")

        # Should show items containing "pr"
        assert widget.list_widget.count() == 2  # print, printf
        assert widget.isVisible()

    def test_completion_filtering_priority(self, qt_app):
        """Test that completions starting with prefix are prioritized."""
        editor = CodeEditor()
        widget = CompletionWidget(editor)

        items = [
            {"label": "import", "kind": 14},
            {"label": "important", "kind": 6},
            {"label": "something_imp", "kind": 6},
        ]

        widget.show_completions(items, "imp")

        # Items starting with "imp" should come first
        first_item = widget.list_widget.item(0)
        assert first_item is not None
        # The display text includes symbols, so check if label is in the text
        assert "import" in first_item.text()

    def test_completion_kinds(self, qt_app):
        """Test completion kind symbols and colors."""
        editor = CodeEditor()
        widget = CompletionWidget(editor)

        items = [
            {"label": "myFunc", "kind": 3},  # Function
            {"label": "MyClass", "kind": 7},  # Class
            {"label": "keyword", "kind": 14},  # Keyword
            {"label": "snippet", "kind": 15},  # Snippet
        ]

        widget.show_completions(items, "")

        assert widget.list_widget.count() == 4
        # Check that different kinds get different symbols
        assert "ƒ" in widget.list_widget.item(0).text()  # Function symbol


class TestIntelliSenseAutoTrigger:
    """Test IntelliSense auto-trigger functionality."""

    def test_config_loading(self, qt_app):
        """Test that IntelliSense config is loaded correctly."""
        config = ConfigManager()
        editor = CodeEditor(config=config)

        assert editor._intellisense_enabled is True
        assert editor._auto_trigger_enabled is True
        assert '.' in editor._trigger_characters
        assert editor._min_chars_for_completion == 1

    def test_auto_trigger_disabled(self, qt_app):
        """Test that auto-trigger can be disabled via config."""
        config = ConfigManager()
        config.set("intellisense", {"enabled": False})
        editor = CodeEditor(config=config)

        assert editor._intellisense_enabled is False

    def test_trigger_characters(self, qt_app):
        """Test that trigger characters are loaded from config."""
        config = ConfigManager()
        editor = CodeEditor(config=config)

        # Default trigger characters should be loaded
        assert '.' in editor._trigger_characters
        assert ':' in editor._trigger_characters
        assert '(' in editor._trigger_characters

    def test_completion_widget_integration(self, qt_app):
        """Test that completion widget is properly integrated."""
        editor = CodeEditor()

        assert hasattr(editor, 'completion_widget')
        assert isinstance(editor.completion_widget, CompletionWidget)
        assert editor.completion_widget.editor == editor

    def test_snippet_manager_integration(self, qt_app):
        """Test that snippet manager is properly integrated."""
        editor = CodeEditor()

        assert hasattr(editor, 'snippet_manager')
        assert isinstance(editor.snippet_manager, SnippetManager)
        assert editor.snippet_manager.editor == editor


class TestEditorKeyPressHandling:
    """Test keyboard event handling for IntelliSense."""

    def test_tab_navigation_in_snippet(self, qt_app):
        """Test Tab key navigates through snippet tab stops."""
        editor = CodeEditor()
        editor.setPlainText("")
        editor.snippet_manager.insert_snippet("${1:first} ${2:second}")

        # Simulate Tab key press
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
        editor.keyPressEvent(event)

        # Should be on second tab stop
        cursor = editor.textCursor()
        assert cursor.selectedText() == "second"

    def test_escape_cancels_snippet(self, qt_app):
        """Test Escape key cancels active snippet."""
        editor = CodeEditor()
        editor.setPlainText("")
        editor.snippet_manager.insert_snippet("${1:first} ${2:second}")

        assert editor.snippet_manager.active_snippet is not None

        # Simulate Escape key press
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        editor.keyPressEvent(event)

        assert editor.snippet_manager.active_snippet is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
