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
    QToolButton,
    QStackedLayout,
)

from ghostline.core.resources import load_icon

class BottomPanelTab(QWidget):
    """A single tab in the bottom panel tab bar."""

    clicked = Signal()

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.is_active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)

        self.label = QLabel(title, self)
        layout.addWidget(self.label)

        self.setObjectName("bottomPanelTab")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, True)

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
    panel_collapse_requested = Signal()
    panel_maximize_requested = Signal()
    panel_close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tabs: list[BottomPanelTab] = []
        self.current_index = 0
        self._controls_for_tab: dict[int, QWidget] = {}

        self.setObjectName("bottomPanelTabBar")
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # Left side: tabs
        self.tab_container = QWidget(self)
        self.tab_layout = QHBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(0, 2, 0, 2)
        self.tab_layout.setSpacing(4)

        layout.addWidget(self.tab_container)
        layout.addStretch(1)

        # Right side: controls
        self.controls_container = QWidget(self)
        self.controls_container.setObjectName("bottomPanelControls")
        self.controls_layout = QHBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(6)

        # Tab-specific controls stack
        self.controls_host = QWidget(self)
        self.controls_stack = QStackedLayout(self.controls_host)
        self.controls_stack.setContentsMargins(0, 0, 0, 0)
        self.controls_stack.setStackingMode(QStackedLayout.StackOne)
        self._placeholder_controls = QWidget(self.controls_host)
        self.controls_stack.addWidget(self._placeholder_controls)
        self.controls_layout.addWidget(self.controls_host)

        # Panel controls (always visible)
        self.panel_menu_btn = self._build_panel_button("bottomPanelMenuBtn", "Panel options")
        self.panel_menu_btn.setIcon(load_icon("terminal_bar/panel-square.svg"))
        self.panel_maximize_btn = self._build_panel_button("bottomPanelMaximizeBtn", "Maximize panel")
        self.panel_maximize_btn.setIcon(load_icon("terminal_bar/maximize.svg"))
        self.panel_close_btn = self._build_panel_button("bottomPanelCloseBtn", "Close Panel")
        self.panel_close_btn.setIcon(load_icon("terminal_bar/close.svg"))

        self.panel_menu_btn.clicked.connect(self.panel_collapse_requested)
        self.panel_maximize_btn.clicked.connect(self.panel_maximize_requested)
        self.panel_close_btn.clicked.connect(self.panel_close_requested)

        self.controls_layout.addWidget(self.panel_menu_btn)
        self.controls_layout.addWidget(self.panel_maximize_btn)
        self.controls_layout.addWidget(self.panel_close_btn)

        layout.addWidget(self.controls_container)

    def _build_panel_button(self, object_name: str, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setAutoRaise(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setProperty("category", "panelBar")
        return button

    def add_tab(self, title: str, controls: QWidget | None = None) -> int:
        """Add a new tab to the tab bar."""
        tab = BottomPanelTab(title, self)
        tab.clicked.connect(lambda: self._on_tab_clicked(tab))

        self.tab_layout.addWidget(tab)
        self.tabs.append(tab)

        tab_index = len(self.tabs) - 1
        if controls is not None:
            self.set_tab_controls(tab_index, controls)

        if tab_index == 0:
            tab.set_active(True)
            self._update_controls(tab_index)

        return tab_index

    def set_tab_controls(self, index: int, controls: QWidget) -> None:
        """Attach a tab-specific controls widget to the bar."""
        if controls not in [self.controls_stack.widget(i) for i in range(self.controls_stack.count())]:
            self.controls_stack.addWidget(controls)
        self._controls_for_tab[index] = controls

    def _on_tab_clicked(self, tab: BottomPanelTab) -> None:
        """Handle tab click."""
        if tab in self.tabs:
            index = self.tabs.index(tab)
            self.set_current_index(index)

    def set_current_index(self, index: int) -> None:
        """Set the currently active tab."""
        if 0 <= index < len(self.tabs):
            for t in self.tabs:
                t.set_active(False)
            self.tabs[index].set_active(True)
            self.current_index = index
            self._update_controls(index)
            self.tab_changed.emit(index)

    def _update_controls(self, index: int) -> None:
        controls = self._controls_for_tab.get(index, self._placeholder_controls)
        self.controls_stack.setCurrentWidget(controls)

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

    def add_panel(self, title: str, widget: QWidget, controls: QWidget | None = None) -> int:
        """Add a new panel with the given title and widget."""
        tab_index = self.tab_bar.add_tab(title, controls)
        self.content_stack.addWidget(widget)
        return tab_index

    def set_current_panel(self, index: int) -> None:
        """Set the currently visible panel."""
        self.tab_bar.set_current_index(index)

    def get_current_panel_index(self) -> int:
        """Get the currently visible panel index."""
        return self.tab_bar.current_index_value()

    def get_close_button(self) -> QPushButton:
        """Get the close button for connecting signals."""
        return self.tab_bar.panel_close_btn
