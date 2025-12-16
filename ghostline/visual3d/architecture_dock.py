"""Dock widget hosting the 3D architecture map.

This module provides the UI container for the architecture visualization,
including controls for:
- Layout algorithm selection
- Filtering and focus modes
- Export functionality
- Camera controls
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ghostline.visual3d.architecture_scene import ArchitectureScene
from ghostline.visual3d.layout_algorithms import LayoutType
from ghostline.visual3d.focus_mode import FilterCriteria, FocusLevel


class ArchitectureDock(QDockWidget):
    """Dockable container for the Ghostline Spatial Map.

    Features:
    - Layout algorithm selector (hierarchical, force-directed, radial, etc.)
    - Node type filters
    - Focus mode controls
    - Search/find nodes
    - Export button
    - Camera controls (reset, zoom to fit)

    Signals:
        open_file_requested: Emitted when user clicks a node to open a file
    """

    open_file_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("3D Architecture Map", parent)
        self._graph: dict | None = None
        self._filtered_graph: dict | None = None
        self._node_lookup: Dict[str, dict] = {}
        self._selected_node: Optional[str] = None

        # Main container
        container = QWidget(self)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- Controls section ---
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Layout selector
        layout_group = self._create_layout_controls()
        controls_layout.addWidget(layout_group)

        # Filter selector
        filter_group = self._create_filter_controls()
        controls_layout.addWidget(filter_group)

        controls_layout.addStretch()

        # Camera and export buttons
        camera_group = self._create_camera_controls()
        controls_layout.addWidget(camera_group)

        main_layout.addLayout(controls_layout)

        # --- Focus mode section ---
        focus_layout = self._create_focus_controls()
        main_layout.addLayout(focus_layout)

        # --- Info label ---
        self.info_label = QLabel(
            "Click nodes to open files. Use scroll wheel to zoom, drag to rotate.",
            self,
        )
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.info_label.setStyleSheet("color: #888; font-size: 11px;")
        main_layout.addWidget(self.info_label)

        # --- 3D Scene ---
        self.scene = ArchitectureScene(self)
        main_layout.addWidget(self.scene, 1)

        # --- Status bar ---
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #aaa; font-size: 10px;")
        main_layout.addWidget(self.status_label)

        self.setWidget(container)

        # Connect signals
        self.scene.node_clicked.connect(self._on_node_clicked)
        self.scene.node_hovered.connect(self._on_node_hovered)
        self.scene.layout_changed.connect(self._on_layout_changed)
        self.scene.animation_finished.connect(self._on_animation_finished)

        # Connect camera control buttons (deferred until self.scene exists)
        self.reset_btn.clicked.connect(self.scene.reset_view)
        self.fit_btn.clicked.connect(self.scene.zoom_to_fit)

    def _create_layout_controls(self) -> QWidget:
        """Create layout algorithm selector."""
        group = QWidget(self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("Layout:", self))

        self.layout_combo = QComboBox(self)
        self.layout_combo.addItem("Hierarchical", LayoutType.HIERARCHICAL)
        self.layout_combo.addItem("Force-Directed", LayoutType.FORCE_DIRECTED)
        self.layout_combo.addItem("Radial", LayoutType.RADIAL)
        self.layout_combo.addItem("Circular", LayoutType.CIRCULAR)
        self.layout_combo.addItem("Grid", LayoutType.GRID)
        self.layout_combo.setToolTip("Select layout algorithm for arranging nodes")
        self.layout_combo.currentIndexChanged.connect(self._on_layout_selected)

        layout.addWidget(self.layout_combo)
        return group

    def _create_filter_controls(self) -> QWidget:
        """Create filter type selector."""
        group = QWidget(self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("Show:", self))

        self.filter_combo = QComboBox(self)
        self.filter_combo.addItem("All", FilterCriteria.ALL)
        self.filter_combo.addItem("Modules", FilterCriteria.MODULES)
        self.filter_combo.addItem("Files", FilterCriteria.FILES)
        self.filter_combo.addItem("Classes", FilterCriteria.CLASSES)
        self.filter_combo.addItem("Functions", FilterCriteria.FUNCTIONS)
        self.filter_combo.setToolTip("Filter nodes by type")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_selected)

        layout.addWidget(self.filter_combo)
        return group

    def _create_focus_controls(self) -> QHBoxLayout:
        """Create focus mode controls."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Search box
        layout.addWidget(QLabel("Find:", self))
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search nodes...")
        self.search_input.setMaximumWidth(150)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # Focus level selector
        layout.addWidget(QLabel("Focus:", self))
        self.focus_combo = QComboBox(self)
        self.focus_combo.addItem("Off", FocusLevel.NONE)
        self.focus_combo.addItem("Highlight", FocusLevel.HIGHLIGHT)
        self.focus_combo.addItem("Neighbors", FocusLevel.NEIGHBORS)
        self.focus_combo.addItem("Extended", FocusLevel.EXTENDED)
        self.focus_combo.addItem("Isolate", FocusLevel.ISOLATE)
        self.focus_combo.setToolTip("Set focus level for selected nodes")
        self.focus_combo.currentIndexChanged.connect(self._on_focus_level_changed)
        layout.addWidget(self.focus_combo)

        # Clear focus button
        self.clear_focus_btn = QPushButton("Clear", self)
        self.clear_focus_btn.setToolTip("Clear focus and show all nodes")
        self.clear_focus_btn.clicked.connect(self._on_clear_focus)
        self.clear_focus_btn.setEnabled(False)
        layout.addWidget(self.clear_focus_btn)

        layout.addStretch()
        return layout

    def _create_camera_controls(self) -> QWidget:
        """Create camera and export controls."""
        group = QWidget(self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Reset camera button (signal connected later after self.scene is created)
        self.reset_btn = QPushButton("Reset", self)
        self.reset_btn.setToolTip("Reset camera to default position")
        layout.addWidget(self.reset_btn)

        # Fit to view button (signal connected later after self.scene is created)
        self.fit_btn = QPushButton("Fit", self)
        self.fit_btn.setToolTip("Fit all nodes in view")
        layout.addWidget(self.fit_btn)

        # Export button with menu
        self.export_btn = QToolButton(self)
        self.export_btn.setText("Export")
        self.export_btn.setToolTip("Export visualization to image or data file")
        self.export_btn.setPopupMode(QToolButton.MenuButtonPopup)

        export_menu = QMenu(self)
        export_menu.addAction("Export as PNG...", lambda: self._export_format("png"))
        export_menu.addAction("Export as SVG...", lambda: self._export_format("svg"))
        export_menu.addAction("Export as JSON...", lambda: self._export_format("json"))
        export_menu.addSeparator()
        export_menu.addAction("Export with options...", self._export_with_dialog)

        self.export_btn.setMenu(export_menu)
        self.export_btn.clicked.connect(self._export_with_dialog)
        layout.addWidget(self.export_btn)

        return group

    # --- Public API ---

    def set_graph(self, graph: dict | None) -> None:
        """Set the graph data and refresh the view."""
        self._graph = graph or {"nodes": [], "edges": []}
        self._node_lookup = {
            node.get("id"): node
            for node in self._graph.get("nodes", [])
            if node.get("id")
        }
        self._update_status()
        self._apply_current_filter()

        # Enable/disable controls based on data
        has_data = bool(self._graph.get("nodes"))
        self.reset_btn.setEnabled(has_data and self.scene.render_available)
        self.fit_btn.setEnabled(has_data and self.scene.render_available)
        self.export_btn.setEnabled(has_data)

    def center_on_node(self, node_id: str) -> None:
        """Center the view on a specific node."""
        self.scene.center_on_node(node_id)

    def focus_on_node(self, node_id: str) -> None:
        """Focus on a specific node with the current focus level."""
        level = self.focus_combo.currentData()
        if level == FocusLevel.NONE:
            level = FocusLevel.NEIGHBORS
            self.focus_combo.setCurrentIndex(
                self.focus_combo.findData(FocusLevel.NEIGHBORS)
            )
        self.scene.focus_on_node(node_id, level)
        self._selected_node = node_id
        self.clear_focus_btn.setEnabled(True)

    def highlight_path_between(self, from_node: str, to_node: str) -> None:
        """Highlight the path between two nodes."""
        self.scene.highlight_path(from_node, to_node)

    # --- Event handlers ---

    def _on_node_clicked(self, node_id: str) -> None:
        """Handle node click event."""
        node = self._node_lookup.get(node_id)
        if not node:
            return

        # If shift is held, focus on the node
        modifiers = QWidget.keyboardModifiers(self)
        if modifiers & Qt.ShiftModifier:
            self.focus_on_node(node_id)
            return

        # Otherwise, open the file
        file_path = node.get("file")
        if not file_path:
            return
        line = node.get("line")
        self.open_file_requested.emit(file_path, line or 0)

    def _on_node_hovered(self, node_id: str) -> None:
        """Handle node hover event."""
        node = self._node_lookup.get(node_id)
        if node:
            label = node.get("label", "")
            node_type = node.get("type", "")
            file_path = node.get("file", "")
            self.info_label.setText(
                f"<b>{label}</b> ({node_type})"
                + (f" - {file_path}" if file_path else "")
            )
        else:
            self.info_label.setText(
                "Click nodes to open files. Use scroll wheel to zoom, drag to rotate."
            )

    def _on_layout_selected(self) -> None:
        """Handle layout algorithm selection."""
        layout_type = self.layout_combo.currentData()
        if layout_type:
            self.scene.set_layout(layout_type, animate=True)

    def _on_layout_changed(self, layout_name: str) -> None:
        """Handle layout change completion."""
        self._update_status()

    def _on_animation_finished(self) -> None:
        """Handle animation completion."""
        pass  # Could update UI state here

    def _on_filter_selected(self) -> None:
        """Handle filter type selection."""
        self._apply_current_filter()

    def _apply_current_filter(self) -> None:
        """Apply the currently selected filter."""
        criteria = self.filter_combo.currentData()
        if criteria:
            self.scene.set_filter(criteria)
            self.scene.set_graph(self._graph)

    def _on_focus_level_changed(self) -> None:
        """Handle focus level change."""
        if self._selected_node:
            level = self.focus_combo.currentData()
            if level == FocusLevel.NONE:
                self.scene.clear_focus()
                self.clear_focus_btn.setEnabled(False)
            else:
                self.scene.focus_on_node(self._selected_node, level)

    def _on_clear_focus(self) -> None:
        """Handle clear focus button click."""
        self.scene.clear_focus()
        self._selected_node = None
        self.clear_focus_btn.setEnabled(False)
        self.focus_combo.setCurrentIndex(0)  # Set to "Off"

    def _on_search_changed(self, text: str) -> None:
        """Handle search input change."""
        if not text:
            return

        text_lower = text.lower()

        # Find matching nodes
        matches = [
            node_id
            for node_id, node in self._node_lookup.items()
            if text_lower in node.get("label", "").lower()
            or text_lower in node.get("file", "").lower()
        ]

        if matches:
            # Center on first match
            self.scene.center_on_node(matches[0])

            # If multiple matches, highlight all
            if len(matches) > 1:
                self.scene.focus_on_nodes(set(matches), FocusLevel.HIGHLIGHT)
                self.clear_focus_btn.setEnabled(True)

    def _update_status(self) -> None:
        """Update the status label."""
        if not self._graph:
            self.status_label.setText("No data loaded")
            return

        nodes = self._graph.get("nodes", [])
        edges = self._graph.get("edges", [])

        # Count by type
        type_counts = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        parts = [f"{len(nodes)} nodes", f"{len(edges)} edges"]
        type_parts = [f"{count} {t}s" for t, count in sorted(type_counts.items())]
        if type_parts:
            parts.append(f"({', '.join(type_parts)})")

        layout_name = self.layout_combo.currentText()
        parts.append(f"| Layout: {layout_name}")

        self.status_label.setText(" ".join(parts))

    # --- Export handlers ---

    def _export_format(self, format_type: str) -> None:
        """Export to a specific format."""
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime

        filter_map = {
            "png": "PNG Image (*.png)",
            "svg": "SVG Vector (*.svg)",
            "json": "JSON Data (*.json)",
        }

        default_name = f"architecture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Visualization",
            default_name,
            filter_map.get(format_type, "All Files (*)"),
        )

        if file_path:
            success = self.scene.export_image(file_path)
            if success:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Visualization exported to:\n{file_path}",
                )

    def _export_with_dialog(self) -> None:
        """Show full export dialog with options."""
        self.scene.export_with_dialog(self)

    # --- Legacy compatibility ---

    def _apply_filter(self) -> None:
        """Legacy method for compatibility - delegates to _apply_current_filter."""
        self._apply_current_filter()
