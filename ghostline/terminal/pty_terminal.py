"""PTY-backed terminal widget with ANSI color support."""
from __future__ import annotations

import os
import sys
import pty
import select
import subprocess
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QFont,
    QKeyEvent,
    QPalette,
)
from PySide6.QtWidgets import QTextEdit


class ANSIParser:
    """Parse ANSI escape sequences and return formatted text."""

    # ANSI color codes to RGB
    COLORS = {
        30: QColor(0, 0, 0),  # Black
        31: QColor(205, 49, 49),  # Red
        32: QColor(13, 188, 121),  # Green
        33: QColor(229, 229, 16),  # Yellow
        34: QColor(36, 114, 200),  # Blue
        35: QColor(188, 63, 188),  # Magenta
        36: QColor(17, 168, 205),  # Cyan
        37: QColor(229, 229, 229),  # White
        90: QColor(102, 102, 102),  # Bright Black
        91: QColor(241, 76, 76),  # Bright Red
        92: QColor(35, 209, 139),  # Bright Green
        93: QColor(245, 245, 67),  # Bright Yellow
        94: QColor(59, 142, 234),  # Bright Blue
        95: QColor(214, 112, 214),  # Bright Magenta
        96: QColor(41, 184, 219),  # Bright Cyan
        97: QColor(255, 255, 255),  # Bright White
    }

    def __init__(self):
        self.current_fg = None
        self.current_bg = None
        self.bold = False
        self.underline = False

    def parse(self, text: str) -> list[tuple[str, QTextCharFormat]]:
        """Parse ANSI text and return list of (text, format) tuples."""
        import re

        result = []
        text = self._strip_unhandled_sequences(text)
        ansi_pattern = re.compile(r"\x1b\[([\d;]*)m")

        pos = 0
        for match in ansi_pattern.finditer(text):
            # Add text before escape sequence
            if match.start() > pos:
                plain_text = text[pos : match.start()]
                result.append((plain_text, self._get_format()))

            # Process escape sequence
            codes = match.group(1)
            if codes:
                self._process_codes(codes)
            else:
                self._reset()

            pos = match.end()

        # Add remaining text
        if pos < len(text):
            result.append((text[pos:], self._get_format()))

        return result

    def _strip_unhandled_sequences(self, text: str) -> str:
        """Remove escape sequences we do not render (titles, bracketed paste, etc.)."""
        import re

        # OSC sequences like terminal titles: ESC ] ... BEL or ESC ] ... ESC \\
        osc_pattern = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
        # CSI sequences that do not end with 'm' (we only render SGR color codes)
        csi_non_sgr_pattern = re.compile(r"\x1b\[[0-9;?]*((?!m)[@-~])")

        text = osc_pattern.sub("", text)
        text = csi_non_sgr_pattern.sub("", text)
        return text

    def _process_codes(self, codes: str) -> None:
        """Process ANSI SGR codes."""
        for code_str in codes.split(";"):
            if not code_str:
                continue
            code = int(code_str)

            if code == 0:
                self._reset()
            elif code == 1:
                self.bold = True
            elif code == 4:
                self.underline = True
            elif 30 <= code <= 37 or 90 <= code <= 97:
                self.current_fg = self.COLORS.get(code)
            elif 40 <= code <= 47:
                self.current_bg = self.COLORS.get(code - 10)
            elif 100 <= code <= 107:
                self.current_bg = self.COLORS.get(code - 10)

    def _reset(self) -> None:
        """Reset formatting."""
        self.current_fg = None
        self.current_bg = None
        self.bold = False
        self.underline = False

    def _get_format(self) -> QTextCharFormat:
        """Get current text format."""
        fmt = QTextCharFormat()
        if self.current_fg:
            fmt.setForeground(self.current_fg)
        if self.current_bg:
            fmt.setBackground(self.current_bg)
        if self.bold:
            fmt.setFontWeight(QFont.Bold)
        if self.underline:
            fmt.setFontUnderline(True)
        return fmt


class PTYSignals(QObject):
    """Signals for PTY output."""

    output_ready = Signal(str)
    process_exited = Signal(int)


class PTYTerminal(QTextEdit):
    """A real PTY-backed terminal widget with ANSI color support."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ptyTerminal")

        # Terminal state
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.shell = os.environ.get("SHELL", "/bin/bash")
        self.working_dir = Path.cwd()
        self.input_buffer = ""

        # ANSI parser
        self.ansi_parser = ANSIParser()

        # Signals
        self.signals = PTYSignals()
        self.signals.output_ready.connect(self._append_output)
        self.signals.process_exited.connect(self._on_process_exited)

        # Setup widget
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)

        # Font
        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # Colors
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.Text, QColor(212, 212, 212))
        self.setPalette(palette)

        # Track cursor position for input
        self.input_start_pos = 0

        # Timer for reading output
        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self._read_output)
        self.read_timer.start(50)  # Read every 50ms

    def start_shell(self, working_dir: Optional[Path] = None) -> None:
        """Start a shell in a PTY."""
        if self.master_fd is not None:
            return  # Already running

        if working_dir:
            self.working_dir = working_dir

        try:
            # Fork a new process with a PTY
            self.pid, self.master_fd = pty.fork()

            if self.pid == 0:
                # Child process
                os.chdir(str(self.working_dir))
                env = os.environ.copy()
                env["TERM"] = "xterm-256color"
                env["PS1"] = "$ "
                os.execvpe(self.shell, [self.shell], env)
            else:
                # Parent process
                # Set non-blocking
                import fcntl

                flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
                fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                # Mark input start
                self.input_start_pos = self.textCursor().position()

        except Exception as e:
            self.append(f"Failed to start shell: {e}")

    def _read_output(self) -> None:
        """Read output from PTY (called by timer)."""
        if self.master_fd is None:
            return

        try:
            # Check if data is available
            readable, _, _ = select.select([self.master_fd], [], [], 0)
            if not readable:
                return

            # Read available data
            data = os.read(self.master_fd, 4096)
            if data:
                text = data.decode("utf-8", errors="replace")
                # Handle special control characters
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                self.signals.output_ready.emit(text)
            else:
                # EOF - process died
                self._cleanup_pty()
                self.signals.process_exited.emit(0)

        except OSError:
            # Process might have died
            pass
        except Exception:
            pass

    def _append_output(self, text: str) -> None:
        """Append output text with ANSI formatting."""
        # Parse ANSI codes
        segments = self.ansi_parser.parse(text)

        # Move cursor to end
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

        # Insert formatted text
        for text_segment, fmt in segments:
            if text_segment:
                cursor.insertText(text_segment, fmt)

        # Update input start position
        self.input_start_pos = self.textCursor().position()

        # Auto-scroll to bottom
        self.ensureCursorVisible()

    def _on_process_exited(self, code: int) -> None:
        """Handle process exit."""
        self.append(f"\n[Process exited with code {code}]\n")
        self._cleanup_pty()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key presses and send to PTY."""
        if self.master_fd is None:
            super().keyPressEvent(event)
            return

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        # Handle special keys
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            # Send newline
            try:
                os.write(self.master_fd, b"\n")
            except OSError:
                pass
            return

        elif key == Qt.Key_Backspace:
            # Prevent deleting prompt
            cursor = self.textCursor()
            if cursor.position() > self.input_start_pos:
                try:
                    os.write(self.master_fd, b"\x7f")  # DEL character
                except OSError:
                    pass
            return

        elif key == Qt.Key_Up:
            try:
                os.write(self.master_fd, b"\x1b[A")  # Up arrow
            except OSError:
                pass
            return

        elif key == Qt.Key_Down:
            try:
                os.write(self.master_fd, b"\x1b[B")  # Down arrow
            except OSError:
                pass
            return

        elif key == Qt.Key_Left:
            try:
                os.write(self.master_fd, b"\x1b[D")  # Left arrow
            except OSError:
                pass
            return

        elif key == Qt.Key_Right:
            try:
                os.write(self.master_fd, b"\x1b[C")  # Right arrow
            except OSError:
                pass
            return

        elif key == Qt.Key_Tab:
            try:
                os.write(self.master_fd, b"\t")
            except OSError:
                pass
            return

        elif key == Qt.Key_C and modifiers & Qt.ControlModifier:
            # Ctrl+C
            try:
                os.write(self.master_fd, b"\x03")
            except OSError:
                pass
            return

        elif key == Qt.Key_D and modifiers & Qt.ControlModifier:
            # Ctrl+D
            try:
                os.write(self.master_fd, b"\x04")
            except OSError:
                pass
            return

        elif key == Qt.Key_L and modifiers & Qt.ControlModifier:
            # Ctrl+L (clear screen)
            try:
                os.write(self.master_fd, b"\x0c")
            except OSError:
                pass
            return

        # Regular text input
        if text:
            try:
                os.write(self.master_fd, text.encode("utf-8"))
            except OSError:
                pass

    def write_input(self, text: str) -> None:
        """Write text input to the terminal."""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, text.encode("utf-8"))
            except OSError:
                pass

    def send_interrupt(self) -> None:
        """Send a Ctrl+C interrupt to the running PTY process."""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, b"\x03")
            except OSError:
                pass

    def clear_output(self) -> None:
        """Clear all terminal output and reset the input start position."""
        self.clear()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.input_start_pos = cursor.position()

    def _cleanup_pty(self) -> None:
        """Clean up PTY resources."""
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        if self.pid is not None:
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except OSError:
                pass
            self.pid = None

    def closeEvent(self, event) -> None:
        """Clean up on close."""
        self.read_timer.stop()
        self._cleanup_pty()
        super().closeEvent(event)

    def get_working_directory(self) -> Path:
        """Get the current working directory of the shell."""
        # Try to read from /proc (Linux only)
        if self.pid:
            try:
                cwd_link = Path(f"/proc/{self.pid}/cwd")
                if cwd_link.exists():
                    return cwd_link.resolve()
            except Exception:
                pass
        return self.working_dir
