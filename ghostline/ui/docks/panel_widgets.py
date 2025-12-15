"""Panel widgets for bottom dock (Problems, Output, Debug Console, Ports)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QPushButton,
    QLineEdit,
)
from PySide6.QtGui import QColor


class ProblemsPanel(QWidget):
    """Problems panel - shows errors, warnings, and info messages."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("problemsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with filter controls
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        # Filter combo
        self.filter_combo = QComboBox(self)
        self.filter_combo.addItems(["All", "Errors", "Warnings", "Info"])
        self.filter_combo.setMaximumWidth(120)
        header_layout.addWidget(QLabel("Filter:", self))
        header_layout.addWidget(self.filter_combo)

        header_layout.addStretch()

        # Summary label
        self.summary_label = QLabel("No problems", self)
        self.summary_label.setStyleSheet("color: #999;")
        header_layout.addWidget(self.summary_label)

        layout.addWidget(header)

        # Problems table
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("problemsTable")
        self.table.setHorizontalHeaderLabels(["Severity", "Message", "File", "Line"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(3, 60)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def add_problem(
        self, severity: str, message: str, file: str, line: int
    ) -> None:
        """Add a problem to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Severity
        severity_item = QTableWidgetItem(severity)
        if severity == "Error":
            severity_item.setForeground(QColor(244, 71, 71))
        elif severity == "Warning":
            severity_item.setForeground(QColor(252, 207, 49))
        else:
            severity_item.setForeground(QColor(75, 166, 251))
        self.table.setItem(row, 0, severity_item)

        # Message
        self.table.setItem(row, 1, QTableWidgetItem(message))

        # File
        self.table.setItem(row, 2, QTableWidgetItem(file))

        # Line
        self.table.setItem(row, 3, QTableWidgetItem(str(line)))

        # Update summary
        self._update_summary()

    def clear_problems(self) -> None:
        """Clear all problems."""
        self.table.setRowCount(0)
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary label."""
        count = self.table.rowCount()
        if count == 0:
            self.summary_label.setText("No problems")
        elif count == 1:
            self.summary_label.setText("1 problem")
        else:
            self.summary_label.setText(f"{count} problems")


class OutputPanel(QWidget):
    """Output panel - shows build/run output."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("outputPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with output source selector
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        header_layout.addWidget(QLabel("Show output from:", self))

        self.source_combo = QComboBox(self)
        self.source_combo.addItems(["Tasks", "Build", "Extension Host", "Git"])
        self.source_combo.setMaximumWidth(150)
        header_layout.addWidget(self.source_combo)

        header_layout.addStretch()

        # Clear button
        self.clear_btn = QPushButton("Clear", self)
        self.clear_btn.setMaximumWidth(60)
        self.clear_btn.clicked.connect(self._clear_output)
        header_layout.addWidget(self.clear_btn)

        layout.addWidget(header)

        # Output text area
        self.output_text = QTextEdit(self)
        self.output_text.setObjectName("outputText")
        self.output_text.setReadOnly(True)
        self.output_text.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.output_text)

    def append_output(self, text: str) -> None:
        """Append text to the output."""
        self.output_text.append(text)

    def _clear_output(self) -> None:
        """Clear the output."""
        self.output_text.clear()


class DebugConsolePanel(QWidget):
    """Debug console panel - for debugger output and REPL."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("debugConsolePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        header_layout.addWidget(QLabel("Debug Console", self))
        header_layout.addStretch()

        # Clear button
        self.clear_btn = QPushButton("Clear", self)
        self.clear_btn.setMaximumWidth(60)
        self.clear_btn.clicked.connect(self._clear_console)
        header_layout.addWidget(self.clear_btn)

        layout.addWidget(header)

        # Console output
        self.console_output = QTextEdit(self)
        self.console_output.setObjectName("debugConsoleOutput")
        self.console_output.setReadOnly(True)
        layout.addWidget(self.console_output)

        # Input area
        input_container = QWidget(self)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(4)

        input_layout.addWidget(QLabel(">", self))

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Evaluate expression...")
        self.input_field.returnPressed.connect(self._evaluate_expression)
        input_layout.addWidget(self.input_field)

        layout.addWidget(input_container)

    def append_console(self, text: str) -> None:
        """Append text to the debug console."""
        self.console_output.append(text)

    def _clear_console(self) -> None:
        """Clear the console."""
        self.console_output.clear()

    def _evaluate_expression(self) -> None:
        """Evaluate expression in debug context."""
        expression = self.input_field.text()
        if expression:
            self.console_output.append(f"> {expression}")
            self.console_output.append(
                "<i>Debug evaluation not yet connected to debugger</i>"
            )
            self.input_field.clear()


class PortsPanel(QWidget):
    """Ports panel - shows forwarded ports and local servers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("portsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        header_layout.addWidget(QLabel("Ports", self))
        header_layout.addStretch()

        # Add port button
        self.add_port_btn = QPushButton("+ Forward Port", self)
        self.add_port_btn.setMaximumWidth(120)
        header_layout.addWidget(self.add_port_btn)

        layout.addWidget(header)

        # Ports table
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("portsTable")
        self.table.setHorizontalHeaderLabels(["Port", "Status", "Label", "Actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 100)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Empty state message
        self.empty_label = QLabel(
            "No forwarded ports.\nForward a port to access local services.", self
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #999; padding: 40px;")
        layout.addWidget(self.empty_label)

        # Show empty state initially
        self.table.hide()

    def add_port(self, port: int, label: str = "", status: str = "Active") -> None:
        """Add a port to the table."""
        if self.table.rowCount() == 0:
            self.empty_label.hide()
            self.table.show()

        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(str(port)))
        self.table.setItem(row, 1, QTableWidgetItem(status))
        self.table.setItem(row, 2, QTableWidgetItem(label or f"Port {port}"))
        self.table.setItem(row, 3, QTableWidgetItem("Open | Stop"))
