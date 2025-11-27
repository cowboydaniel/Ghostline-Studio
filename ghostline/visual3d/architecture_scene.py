"""Qt3D-based visualization for the Ghostline Spatial Map."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, pi
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QQuaternion, QVector3D
from PySide6.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget

try:  # Qt3D is optional in some PySide6 builds
    from PySide6.Qt3DCore import Qt3DCore
    from PySide6.Qt3DExtras import Qt3DExtras
    from PySide6.Qt3DRender import Qt3DRender

    QT3D_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without Qt3D
    QT3D_AVAILABLE = False


@dataclass
class _GraphNode:
    node_id: str
    node_type: str
    label: str
    file: Optional[str]
    line: Optional[int]


class ArchitectureScene(QWidget):
    """Widget that displays a semantic graph in 3D when Qt3D is available."""

    node_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._graph: dict | None = None
        self._node_lookup: Dict[str, _GraphNode] = {}
        self._node_entities: Dict[str, Qt3DCore.QEntity] = {}
        self._edge_entities: list[Qt3DCore.QEntity] = []
        self._positions: Dict[str, QVector3D] = {}
        self._render_available = False

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        fallback_label = QLabel(self)
        fallback_label.setWordWrap(True)
        fallback_label.setAlignment(Qt.AlignCenter)
        self._fallback_label = fallback_label
        self._update_placeholder(has_nodes=False)
        self._stack.addWidget(fallback_label)

        if QT3D_AVAILABLE:
            self._setup_3d()
        else:
            placeholder_container = QWidget(self)
            container_layout = QVBoxLayout(placeholder_container)
            container_layout.addWidget(self._fallback_label)
            self._stack.setCurrentWidget(self._fallback_label)

    # --- Public API -----------------------------------------------------
    def set_graph(self, graph: dict | None) -> None:
        """Render a new graph snapshot."""

        self._graph = graph or {"nodes": [], "edges": []}
        has_nodes = bool(self._graph.get("nodes"))
        self._update_placeholder(has_nodes)
        self._render_available = QT3D_AVAILABLE and has_nodes
        if QT3D_AVAILABLE and has_nodes:
            self._build_scene()
            if self._stack.count() > 1:
                self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def center_on_node(self, node_id: str) -> None:
        if not QT3D_AVAILABLE:
            return
        if node_id not in self._positions:
            return
        camera = self._window.camera()
        camera.setViewCenter(self._positions[node_id])

    def reset_view(self) -> None:
        if not self._render_available:
            return
        camera = self._window.camera()
        camera.setPosition(QVector3D(0, 20, 40))
        camera.setViewCenter(QVector3D(0, 0, 0))

    @property
    def render_available(self) -> bool:
        return self._render_available

    # --- Scene construction --------------------------------------------
    def _setup_3d(self) -> None:
        self._window = Qt3DExtras.Qt3DWindow()
        container = QWidget.createWindowContainer(self._window, self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)
        view_container = QWidget(self)
        view_container.setLayout(layout)
        self._stack.addWidget(view_container)

        self._root_entity = Qt3DCore.QEntity()
        self._window.setRootEntity(self._root_entity)

        camera = self._window.camera()
        camera.lens().setPerspectiveProjection(45.0, 16 / 9, 0.1, 1000)
        camera.setPosition(QVector3D(0, 20, 40))
        camera.setViewCenter(QVector3D(0, 0, 0))

        self._controller = Qt3DExtras.QOrbitCameraController(self._root_entity)
        self._controller.setCamera(camera)
        self._controller.setLookSpeed(120)
        self._controller.setLinearSpeed(50)

        light = Qt3DCore.QEntity(self._root_entity)
        light_component = Qt3DRender.QPointLight(light)
        light_component.setColor(QColor(255, 255, 255))
        light_component.setIntensity(0.8)
        light.addComponent(light_component)
        light_transform = Qt3DCore.QTransform()
        light_transform.setTranslation(QVector3D(0, 40, 40))
        light.addComponent(light_transform)

    def _clear_scene(self) -> None:
        for entity in self._node_entities.values():
            entity.setParent(None)
        for entity in self._edge_entities:
            entity.setParent(None)
        self._node_entities.clear()
        self._edge_entities.clear()
        self._positions.clear()

    def _update_placeholder(self, has_nodes: bool) -> None:
        if not QT3D_AVAILABLE:
            message = (
                "3D Architecture Map requires Qt3D support. Install a PySide6 build with "
                "Qt3D enabled to view the semantic graph."
            )
        elif not has_nodes:
            message = (
                "Semantic graph not available yet. Open a workspace or wait for indexing to "
                "finish, then refresh the Architecture Map."
            )
        else:
            message = ""

        if message:
            self._fallback_label.setText(message)

    def _build_scene(self) -> None:
        if self._graph is None:
            return
        self._clear_scene()

        nodes = [
            _GraphNode(
                node_id=node.get("id", node.get("label", "")),
                node_type=node.get("type", "unknown"),
                label=node.get("label", ""),
                file=node.get("file"),
                line=node.get("line"),
            )
            for node in self._graph.get("nodes", [])
        ]
        self._node_lookup = {node.node_id: node for node in nodes}

        self._positions = self._compute_positions(nodes, self._graph.get("edges", []))
        for node in nodes:
            position = self._positions.get(node.node_id, QVector3D(0, 0, 0))
            entity = self._create_node_entity(node, position)
            self._node_entities[node.node_id] = entity

        for edge in self._graph.get("edges", []):
            source_pos = self._positions.get(edge.get("source"))
            target_pos = self._positions.get(edge.get("target"))
            if source_pos and target_pos:
                self._edge_entities.append(self._create_edge_entity(source_pos, target_pos, edge.get("type", "")))

    def _compute_positions(self, nodes: Iterable[_GraphNode], edges: List[dict]) -> Dict[str, QVector3D]:
        positions: Dict[str, QVector3D] = {}
        modules = [n for n in nodes if n.node_type == "module"]
        files = [n for n in nodes if n.node_type == "file"]
        symbols = [n for n in nodes if n.node_type not in {"module", "file"}]

        radius = 25.0
        for idx, module in enumerate(modules or nodes):
            angle = 2 * pi * idx / max(len(modules), 1)
            positions[module.node_id] = QVector3D(radius * cos(angle), 0, radius * sin(angle))

        contains_map = {edge.get("target"): edge.get("source") for edge in edges if edge.get("type") == "contains"}

        def _child_offset(index: int, scale: float) -> QVector3D:
            angle = 2 * pi * (index % 12) / 12
            return QVector3D(scale * cos(angle), 0, scale * sin(angle))

        for idx, file_node in enumerate(files):
            parent = contains_map.get(file_node.node_id)
            origin = positions.get(parent, QVector3D(0, 0, 0))
            positions[file_node.node_id] = origin + _child_offset(idx, 6.0)

        for idx, sym_node in enumerate(symbols):
            parent = contains_map.get(sym_node.node_id)
            origin = positions.get(parent, QVector3D(0, 0, 0))
            positions[sym_node.node_id] = origin + _child_offset(idx, 2.5)

        return positions

    def _create_node_entity(self, node: _GraphNode, position: QVector3D) -> Qt3DCore.QEntity:
        entity = Qt3DCore.QEntity(self._root_entity)
        transform = Qt3DCore.QTransform()
        transform.setTranslation(position)
        entity.addComponent(transform)

        if node.node_type == "module":
            mesh: Qt3DRender.QGeometryRenderer = Qt3DExtras.QCuboidMesh()
            mesh.setXExtent(4.0)
            mesh.setYExtent(2.0)
            mesh.setZExtent(4.0)
            material_color = QColor(0, 122, 204)
        elif node.node_type == "file":
            mesh = Qt3DExtras.QCuboidMesh()
            mesh.setXExtent(2.5)
            mesh.setYExtent(1.5)
            mesh.setZExtent(2.5)
            material_color = QColor(70, 180, 130)
        else:
            mesh = Qt3DExtras.QSphereMesh()
            mesh.setRadius(1.0)
            material_color = QColor(220, 140, 70)

        material = Qt3DExtras.QPhongMaterial(entity)
        material.setDiffuse(material_color)

        picker = Qt3DRender.QObjectPicker(entity)
        picker.setHoverEnabled(True)
        picker.clicked.connect(lambda _event, nid=node.node_id: self.node_clicked.emit(nid))

        entity.addComponent(mesh)
        entity.addComponent(material)
        entity.addComponent(picker)
        return entity

    def _create_edge_entity(self, source: QVector3D, target: QVector3D, relation: str) -> Qt3DCore.QEntity:
        entity = Qt3DCore.QEntity(self._root_entity)
        length = source.distanceToPoint(target)
        mesh = Qt3DExtras.QCylinderMesh()
        mesh.setRadius(0.1 if relation == "contains" else 0.15)
        mesh.setLength(length)

        transform = Qt3DCore.QTransform()
        midpoint = (source + target) / 2
        transform.setTranslation(midpoint)
        direction = target - source
        up = QVector3D(0, 1, 0)
        rotation = QQuaternion.rotationTo(up, direction.normalized()) if not direction.isNull() else QQuaternion()
        transform.setRotation(rotation)

        material = Qt3DExtras.QPhongMaterial(entity)
        if relation == "contains":
            material.setDiffuse(QColor(160, 160, 160))
        else:
            material.setDiffuse(QColor(230, 90, 90))

        entity.addComponent(mesh)
        entity.addComponent(transform)
        entity.addComponent(material)
        return entity
