"""Bottom panel with Windsurf-style tabs (Problems | Output | Debug Console | Terminal | Ports)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QSizePolicy,
)


class BottomPanelTab(QWidget):
    """A single tab in the bottom panel tab bar."""

    clicked = Signal()

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.is_active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(0)

        self.label = QLabel(title, self)
        layout.addWidget(self.label)

        self.setObjectName("bottomPanelTab")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def mousePressEvent(self, event) -> None:
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        """Set the active state of the tab."""
        self.is_active = active
        if active:
            self.setProperty("active", "true")
        else:
            self.setProperty("active", "false")
        # Force style refresh
        self.style().unpolish(self)
        self.style().polish(self)


class BottomPanelTabBar(QWidget):
    """Tab bar for the bottom panel (Windsurf style)."""

    tab_changed = Signal(int)  # Emits the index of the selected tab

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tabs = []
        self.current_index = 0

        self.setObjectName("bottomPanelTabBar")
        self.setFixedHeight(35)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left side: tabs
        self.tab_container = QWidget(self)
        self.tab_layout = QHBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(4, 0, 4, 0)
        self.tab_layout.setSpacing(2)
        self.tab_layout.addStretch()

        layout.addWidget(self.tab_container, stretch=1)

        # Right side: controls (close button, etc.)
        self.controls_container = QWidget(self)
        self.controls_layout = QHBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(4, 0, 4, 0)
        self.controls_layout.setSpacing(4)

        # Close button for bottom panel
        self.close_btn = QPushButton("×", self)
        self.close_btn.setObjectName("bottomPanelCloseBtn")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Close Panel")
        self.controls_layout.addWidget(self.close_btn)

        layout.addWidget(self.controls_container)

    def add_tab(self, title: str) -> int:
        """Add a new tab to the tab bar."""
        tab = BottomPanelTab(title, self)
        tab.clicked.connect(lambda: self._on_tab_clicked(tab))

        # Insert before stretch
        index = self.tab_layout.count() - 1
        self.tab_layout.insertWidget(index, tab)
        self.tabs.append(tab)

        tab_index = len(self.tabs) - 1
        if tab_index == 0:
            tab.set_active(True)

        return tab_index

    def _on_tab_clicked(self, tab: BottomPanelTab) -> None:
        """Handle tab click."""
        if tab in self.tabs:
            index = self.tabs.index(tab)
            self.set_current_index(index)

    def set_current_index(self, index: int) -> None:
        """Set the currently active tab."""
        if 0 <= index < len(self.tabs):
            # Deactivate all tabs
            for t in self.tabs:
                t.set_active(False)
            # Activate selected tab
            self.tabs[index].set_active(True)
            self.current_index = index
            self.tab_changed.emit(index)

    def current_index_value(self) -> int:
        """Get the current tab index."""
        return self.current_index


class BottomPanel(QWidget):
    """Complete bottom panel with tabs and content area."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab bar
        self.tab_bar = BottomPanelTabBar(self)
        layout.addWidget(self.tab_bar)

        # Separator line
        separator = QWidget(self)
        separator.setObjectName("bottomPanelSeparator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Content stack
        self.content_stack = QStackedWidget(self)
        layout.addWidget(self.content_stack)

        # Connect tab bar to content stack
        self.tab_bar.tab_changed.connect(self.content_stack.setCurrentIndex)

        # Minimum height for the panel
        self.setMinimumHeight(150)

    def add_panel(self, title: str, widget: QWidget) -> int:
        """Add a new panel with the given title and widget."""
        tab_index = self.tab_bar.add_tab(title)
        self.content_stack.addWidget(widget)
        return tab_index

    def set_current_panel(self, index: int) -> None:
        """Set the currently visible panel."""
        self.tab_bar.set_current_index(index)

    def get_close_button(self) -> QPushButton:
        """Get the close button for connecting signals."""
        return self.tab_bar.close_btn
