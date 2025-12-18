"""Windows-compatible terminal widget using QProcess."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QProcess
from PySide6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QFont,
    QKeyEvent,
    QPalette,
)
from PySide6.QtWidgets import QTextEdit


class WindowsTerminal(QTextEdit):
    """A Windows-compatible terminal widget using QProcess for cmd.exe or PowerShell."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("windowsTerminal")

        # Process state
        self.process: Optional[QProcess] = None
        self.shell = "powershell.exe" if sys.platform == 'win32' else "cmd.exe"
        self.working_dir = Path.cwd()
        self.input_buffer = ""

        # Setup widget
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)

        # Font
        font = QFont("Consolas", 10) if sys.platform == 'win32' else QFont("Courier New", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # Colors
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(12, 12, 12))
        palette.setColor(QPalette.Text, QColor(204, 204, 204))
        self.setPalette(palette)

        # Track cursor position for input
        self.input_start_pos = 0

    def start_shell(self, working_dir: Optional[Path] = None) -> None:
        """Start a shell using QProcess."""
        if self.process is not None:
            return  # Already running

        if working_dir:
            self.working_dir = working_dir

        # Create process
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.working_dir))

        # Connect signals
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)

        # Configure for interactive use
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        # Start shell
        if sys.platform == 'win32':
            # Use PowerShell on Windows for better experience
            self.shell = "powershell.exe"
            args = [
                "-NoLogo",
                "-NoExit",
                "-ExecutionPolicy", "Bypass"
            ]
            self.process.start(self.shell, args)
        else:
            # Fallback for other platforms (should use PTYTerminal instead)
            self.shell = "cmd.exe"
            self.process.start(self.shell)

        # Wait for process to start
        if not self.process.waitForStarted(3000):
            self.append("Failed to start shell\n")
            return

        # Mark input start
        self.input_start_pos = self.textCursor().position()

    def _on_stdout(self) -> None:
        """Handle stdout from process."""
        if self.process:
            data = self.process.readAllStandardOutput()
            text = bytes(data).decode('utf-8', errors='replace')
            self._append_output(text)

    def _on_stderr(self) -> None:
        """Handle stderr from process."""
        if self.process:
            data = self.process.readAllStandardError()
            text = bytes(data).decode('utf-8', errors='replace')
            self._append_output(text, is_error=True)

    def _append_output(self, text: str, is_error: bool = False) -> None:
        """Append output text to the terminal."""
        # Move cursor to end
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

        # Apply formatting
        fmt = QTextCharFormat()
        if is_error:
            fmt.setForeground(QColor(255, 100, 100))
        else:
            fmt.setForeground(QColor(204, 204, 204))

        # Insert text
        cursor.insertText(text, fmt)

        # Update input start position
        self.input_start_pos = self.textCursor().position()

        # Auto-scroll to bottom
        self.ensureCursorVisible()

    def _on_finished(self, exit_code: int, exit_status) -> None:
        """Handle process exit."""
        self.append(f"\n[Process exited with code {exit_code}]\n")
        if self.process:
            self.process.deleteLater()
            self.process = None

    def _on_error(self, error) -> None:
        """Handle process errors."""
        error_messages = {
            QProcess.FailedToStart: "Failed to start shell",
            QProcess.Crashed: "Shell crashed",
            QProcess.Timedout: "Shell timed out",
            QProcess.WriteError: "Write error",
            QProcess.ReadError: "Read error",
            QProcess.UnknownError: "Unknown error",
        }
        self.append(f"\nError: {error_messages.get(error, 'Unknown error')}\n")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key presses and send to process."""
        if self.process is None or self.process.state() != QProcess.Running:
            super().keyPressEvent(event)
            return

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        # Handle special keys
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            # Get the input text
            cursor = self.textCursor()
            cursor.setPosition(self.input_start_pos)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            input_text = cursor.selectedText()

            # Clear selection
            cursor.clearSelection()
            self.setTextCursor(cursor)

            # Send newline to process
            self.process.write(b"\n")
            self.input_buffer = ""
            return

        elif key == Qt.Key_Backspace:
            # Prevent deleting prompt
            cursor = self.textCursor()
            if cursor.position() > self.input_start_pos:
                # Send backspace to process
                self.process.write(b"\x08")
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                # Actually delete the character in the widget
                super().keyPressEvent(event)
            return

        elif key == Qt.Key_C and modifiers & Qt.ControlModifier:
            # Ctrl+C - send interrupt
            self.process.write(b"\x03")
            self.input_buffer = ""
            return

        elif key == Qt.Key_D and modifiers & Qt.ControlModifier:
            # Ctrl+D - send EOF
            self.process.write(b"\x04")
            return

        elif key == Qt.Key_Up:
            # Up arrow - command history (handled by shell)
            self.process.write(b"\x1b[A")
            return

        elif key == Qt.Key_Down:
            # Down arrow
            self.process.write(b"\x1b[B")
            return

        elif key == Qt.Key_Left:
            # Left arrow
            cursor = self.textCursor()
            if cursor.position() > self.input_start_pos:
                super().keyPressEvent(event)
            return

        elif key == Qt.Key_Right:
            # Right arrow
            super().keyPressEvent(event)
            return

        elif key == Qt.Key_Tab:
            # Tab completion (handled by shell)
            self.process.write(b"\t")
            return

        # Regular text input
        if text:
            # Write to process
            self.process.write(text.encode('utf-8'))
            self.input_buffer += text
            # Display in widget
            super().keyPressEvent(event)

    def write_input(self, text: str) -> None:
        """Write text input to the terminal."""
        if self.process and self.process.state() == QProcess.Running:
            self.process.write(text.encode('utf-8'))

    def send_interrupt(self) -> None:
        """Send a Ctrl+C interrupt to the running process."""
        if self.process and self.process.state() == QProcess.Running:
            # On Windows, we can try to kill or send Ctrl+C
            if sys.platform == 'win32':
                # Windows doesn't have signals like Unix
                # We can try to terminate gracefully
                self.process.write(b"\x03")
            else:
                self.process.terminate()

    def clear_output(self) -> None:
        """Clear all terminal output."""
        self.clear()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.input_start_pos = cursor.position()
        self.input_buffer = ""

    def get_working_directory(self) -> Path:
        """Get the current working directory."""
        return self.working_dir

    def closeEvent(self, event) -> None:
        """Clean up on close."""
        if self.process:
            if self.process.state() == QProcess.Running:
                self.process.terminate()
                self.process.waitForFinished(1000)
                if self.process.state() == QProcess.Running:
                    self.process.kill()
            self.process.deleteLater()
            self.process = None
        super().closeEvent(event)

    def __del__(self) -> None:
        """Ensure cleanup even if closeEvent isn't called."""
        try:
            if self.process:
                if self.process.state() == QProcess.Running:
                    self.process.terminate()
                    self.process.waitForFinished(1000)
                    if self.process.state() == QProcess.Running:
                        self.process.kill()
        except Exception:
            # Ignore errors during cleanup in __del__
            pass
