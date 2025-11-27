"""Dock widget hosting the 3D architecture map."""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDockWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ghostline.visual3d.architecture_scene import ArchitectureScene


class ArchitectureDock(QDockWidget):
    """Dockable container for the Ghostline Spatial Map."""

    open_file_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("3D Architecture Map", parent)
        self._graph: dict | None = None
        self._filtered_graph: dict | None = None
        self._node_lookup: Dict[str, dict] = {}

        self.scene = ArchitectureScene(self)
        self.filter_combo = QComboBox(self)
        self.filter_combo.addItems(["All", "Modules", "Files", "Functions"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)

        self.reset_btn = QPushButton("Reset Camera", self)
        self.reset_btn.clicked.connect(self.scene.reset_view)

        info_label = QLabel("Click nodes to open files/functions in the editor.", self)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Show:", self))
        control_layout.addWidget(self.filter_combo, 1)
        control_layout.addWidget(self.reset_btn)

        layout = QVBoxLayout()
        layout.addLayout(control_layout)
        layout.addWidget(info_label)
        layout.addWidget(self.scene, 1)

        container = QWidget(self)
        container.setLayout(layout)
        self.setWidget(container)

        self.scene.node_clicked.connect(self._on_node_clicked)

    # ------------------------------------------------------------------
    def set_graph(self, graph: dict | None) -> None:
        self._graph = graph or {"nodes": [], "edges": []}
        self._node_lookup = {node.get("id"): node for node in self._graph.get("nodes", []) if node.get("id")}
        self._apply_filter()
        self.reset_btn.setEnabled(self.scene.render_available)

    def center_on_node(self, node_id: str) -> None:
        self.scene.center_on_node(node_id)

    # ------------------------------------------------------------------
    def _apply_filter(self) -> None:
        if self._graph is None:
            return
        selection = self.filter_combo.currentText()
        if selection == "Modules":
            allowed = {"module"}
        elif selection == "Files":
            allowed = {"file"}
        elif selection == "Functions":
            allowed = {"function", "class"}
        else:
            allowed = None

        if allowed is None:
            nodes = list(self._graph.get("nodes", []))
        else:
            nodes = [node for node in self._graph.get("nodes", []) if node.get("type") in allowed]

        node_ids = {node.get("id") for node in nodes}
        edges = [
            edge
            for edge in self._graph.get("edges", [])
            if edge.get("source") in node_ids and edge.get("target") in node_ids
        ]
        self._filtered_graph = {"nodes": nodes, "edges": edges}
        self.scene.set_graph(self._filtered_graph)

    def _on_node_clicked(self, node_id: str) -> None:
        node = self._node_lookup.get(node_id)
        if not node:
            return
        file_path = node.get("file")
        if not file_path:
            return
        line = node.get("line")
        self.open_file_requested.emit(file_path, line or 0)
