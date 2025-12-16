"""Qt3D-based visualization for the Ghostline Spatial Map.

This module provides the core 3D rendering for architecture visualization using Qt3D.
When Qt3D is not available, it falls back to a 2D QPainter-based renderer.

Features:
- Hardware-accelerated 3D rendering with Qt3D
- OpenGL fallback for environments without Qt3D
- Multiple layout algorithms (force-directed, hierarchical, radial, etc.)
- Smooth animation transitions
- Focus mode and filtering
- Export to images
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, pi
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QQuaternion, QVector3D
from PySide6.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget

from ghostline.visual3d.layout_algorithms import (
    LayoutConfig,
    LayoutType,
    compute_graph_layout,
)
from ghostline.visual3d.animation import (
    AnimationController,
    EasingType,
    TransitionManager,
)
from ghostline.visual3d.focus_mode import (
    FilterCriteria,
    FocusLevel,
    FocusModeManager,
    NodeVisibility,
    filter_graph_by_visibility,
)
from ghostline.visual3d.export import ExportManager, ExportConfig, quick_export_png

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
    """Widget that displays a semantic graph in 3D when Qt3D is available.

    Features:
    - Qt3D rendering when available, fallback to 2D otherwise
    - Multiple layout algorithms
    - Smooth transitions between layouts
    - Focus mode for node isolation
    - Export capabilities

    Signals:
        node_clicked: Emitted when a node is clicked (node_id)
        node_hovered: Emitted when a node is hovered (node_id)
        layout_changed: Emitted when layout algorithm changes
        animation_finished: Emitted when animation completes
    """

    node_clicked = Signal(str)
    node_hovered = Signal(str)
    layout_changed = Signal(str)
    animation_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._graph: dict | None = None
        self._node_lookup: Dict[str, _GraphNode] = {}
        self._node_entities: Dict[str, "Qt3DCore.QEntity"] = {}
        self._edge_entities: list["Qt3DCore.QEntity"] = []
        self._positions: Dict[str, QVector3D] = {}
        self._render_available = False

        # Layout settings
        self._current_layout = LayoutType.HIERARCHICAL
        self._layout_config = LayoutConfig()

        # Animation
        self._transition_manager = TransitionManager(
            duration_ms=400,
            easing=EasingType.EASE_OUT,
            parent=self,
        )
        self._transition_manager.transition_finished.connect(self.animation_finished.emit)

        # Focus mode
        self._focus_manager = FocusModeManager(self)
        self._focus_manager.visibility_changed.connect(self._on_visibility_changed)

        # Export manager
        self._export_manager = ExportManager()

        # Material references for opacity control
        self._node_materials: Dict[str, "Qt3DExtras.QPhongAlphaMaterial"] = {}
        self._edge_materials: List["Qt3DExtras.QPhongMaterial"] = []

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        fallback_label = QLabel(self)
        fallback_label.setWordWrap(True)
        fallback_label.setAlignment(Qt.AlignCenter)
        self._fallback_label = fallback_label
        self._update_placeholder(has_nodes=False)
        self._stack.addWidget(fallback_label)

        # Fallback renderer (import here to avoid circular dependency)
        self._fallback_renderer: Optional["FallbackRenderer"] = None

        if QT3D_AVAILABLE:
            self._setup_3d()
        else:
            self._setup_fallback()

    # --- Public API -----------------------------------------------------

    def set_graph(self, graph: dict | None) -> None:
        """Render a new graph snapshot."""
        self._graph = graph or {"nodes": [], "edges": []}
        has_nodes = bool(self._graph.get("nodes"))
        self._update_placeholder(has_nodes)

        # Update focus manager
        self._focus_manager.set_graph(self._graph)

        self._render_available = (QT3D_AVAILABLE or self._fallback_renderer) and has_nodes

        if has_nodes:
            self._build_scene()
            if self._stack.count() > 1:
                self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def set_layout(self, layout_type: LayoutType, animate: bool = True) -> None:
        """Change the layout algorithm.

        Args:
            layout_type: The layout algorithm to use
            animate: Whether to animate the transition
        """
        old_positions = dict(self._positions)
        self._current_layout = layout_type
        self._layout_config.use_3d = QT3D_AVAILABLE

        if not self._graph:
            return

        # Compute new positions
        new_positions = compute_graph_layout(
            self._graph.get("nodes", []),
            self._graph.get("edges", []),
            layout_type,
            self._layout_config,
        )

        if animate and old_positions:
            self._animate_to_positions(old_positions, new_positions)
        else:
            self._positions = new_positions
            self._update_node_positions()

        self.layout_changed.emit(layout_type.value)

        # Update fallback renderer if using it
        if self._fallback_renderer:
            self._fallback_renderer.set_layout(layout_type)

    def center_on_node(self, node_id: str) -> None:
        """Center view on a specific node."""
        if not QT3D_AVAILABLE:
            if self._fallback_renderer:
                self._fallback_renderer.center_on_node(node_id)
            return

        if node_id not in self._positions:
            return

        target_center = self._positions[node_id]
        camera = self._window.camera()
        current_pos = camera.position()
        current_center = camera.viewCenter()

        # Calculate new camera position to center on node
        offset = current_pos - current_center
        new_center = target_center
        new_pos = target_center + offset

        # Animate camera movement
        self._transition_manager.animate_camera_to(
            new_pos,
            new_center,
            current_pos,
            current_center,
            self._update_camera,
        )

    def reset_view(self) -> None:
        """Reset camera to default position."""
        if not self._render_available:
            return

        if QT3D_AVAILABLE:
            camera = self._window.camera()
            current_pos = camera.position()
            current_center = camera.viewCenter()
            default_pos = QVector3D(0, 20, 40)
            default_center = QVector3D(0, 0, 0)

            self._transition_manager.animate_camera_to(
                default_pos,
                default_center,
                current_pos,
                current_center,
                self._update_camera,
            )
        elif self._fallback_renderer:
            self._fallback_renderer.reset_view()

    def zoom_to_fit(self) -> None:
        """Adjust camera to fit all nodes in view."""
        if self._fallback_renderer:
            self._fallback_renderer.zoom_to_fit()
            return

        if not QT3D_AVAILABLE or not self._positions:
            return

        # Calculate bounding sphere
        center = QVector3D(0, 0, 0)
        for pos in self._positions.values():
            center += pos
        center /= len(self._positions)

        max_dist = 0.0
        for pos in self._positions.values():
            dist = (pos - center).length()
            max_dist = max(max_dist, dist)

        # Position camera to fit
        distance = max_dist * 2.5 + 20
        camera_pos = center + QVector3D(0, distance * 0.5, distance)

        camera = self._window.camera()
        self._transition_manager.animate_camera_to(
            camera_pos,
            center,
            camera.position(),
            camera.viewCenter(),
            self._update_camera,
        )

    # --- Focus Mode API ---

    def focus_on_node(self, node_id: str, level: FocusLevel = FocusLevel.NEIGHBORS) -> None:
        """Focus on a specific node, showing only related nodes."""
        self._focus_manager.focus_on_node(node_id, level)
        self.center_on_node(node_id)

    def focus_on_nodes(self, node_ids: set[str], level: FocusLevel = FocusLevel.NEIGHBORS) -> None:
        """Focus on multiple nodes."""
        self._focus_manager.focus_on(node_ids, level)

    def highlight_path(self, from_node: str, to_node: str) -> None:
        """Highlight the path between two nodes."""
        self._focus_manager.highlight_path(from_node, to_node)

    def clear_focus(self) -> None:
        """Clear focus and show all nodes."""
        self._focus_manager.clear_focus()

    def set_filter(self, criteria: FilterCriteria, **kwargs) -> None:
        """Set filter criteria."""
        self._focus_manager.set_filter(criteria, **kwargs)

    # --- Export API ---

    def export_image(self, file_path: str) -> bool:
        """Export the visualization to an image file."""
        if self._fallback_renderer:
            return self._fallback_renderer.export_to_file(file_path)

        # For Qt3D, grab the window contents
        return quick_export_png(self, file_path)

    def export_with_dialog(self, parent: QWidget) -> Optional[str]:
        """Show export dialog and export if confirmed."""
        positions_2d = {
            nid: (pos.x(), pos.z())
            for nid, pos in self._positions.items()
        }
        self._export_manager.set_graph_data(self._graph or {}, positions_2d)

        widget = self._fallback_renderer if self._fallback_renderer else self
        return self._export_manager.export_dialog(parent, widget)

    @property
    def render_available(self) -> bool:
        return self._render_available

    @property
    def current_layout(self) -> LayoutType:
        return self._current_layout

    @property
    def focus_manager(self) -> FocusModeManager:
        return self._focus_manager

    # --- Scene construction --------------------------------------------

    def _setup_3d(self) -> None:
        """Initialize Qt3D rendering."""
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

        # Main light
        light = Qt3DCore.QEntity(self._root_entity)
        light_component = Qt3DRender.QPointLight(light)
        light_component.setColor(QColor(255, 255, 255))
        light_component.setIntensity(0.8)
        light.addComponent(light_component)
        light_transform = Qt3DCore.QTransform()
        light_transform.setTranslation(QVector3D(0, 40, 40))
        light.addComponent(light_transform)

        # Ambient light for softer shadows
        ambient_light = Qt3DCore.QEntity(self._root_entity)
        ambient_component = Qt3DRender.QPointLight(ambient_light)
        ambient_component.setColor(QColor(200, 200, 220))
        ambient_component.setIntensity(0.3)
        ambient_light.addComponent(ambient_component)
        ambient_transform = Qt3DCore.QTransform()
        ambient_transform.setTranslation(QVector3D(-30, 20, -30))
        ambient_light.addComponent(ambient_transform)

    def _setup_fallback(self) -> None:
        """Initialize fallback 2D renderer."""
        from ghostline.visual3d.fallback_renderer import FallbackRenderer

        self._fallback_renderer = FallbackRenderer(self)
        self._fallback_renderer.node_clicked.connect(self.node_clicked.emit)
        self._fallback_renderer.node_hovered.connect(self.node_hovered.emit)
        self._stack.addWidget(self._fallback_renderer)

    def _clear_scene(self) -> None:
        """Remove all nodes and edges from the scene."""
        for entity in self._node_entities.values():
            entity.setParent(None)
        for entity in self._edge_entities:
            entity.setParent(None)
        self._node_entities.clear()
        self._edge_entities.clear()
        self._node_materials.clear()
        self._edge_materials.clear()
        self._positions.clear()

    def _update_placeholder(self, has_nodes: bool) -> None:
        """Update placeholder message based on state."""
        if not QT3D_AVAILABLE and not self._fallback_renderer:
            message = (
                "3D Architecture Map is using fallback rendering mode. "
                "Install PySide6 with Qt3D support for hardware-accelerated 3D visualization."
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
        """Build the 3D scene from graph data."""
        if self._graph is None:
            return

        # Use fallback renderer if Qt3D not available
        if not QT3D_AVAILABLE:
            if self._fallback_renderer:
                self._fallback_renderer.set_graph(self._graph)
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

        # Compute positions using selected layout
        self._positions = compute_graph_layout(
            self._graph.get("nodes", []),
            self._graph.get("edges", []),
            self._current_layout,
            self._layout_config,
        )

        # Create node entities
        for node in nodes:
            position = self._positions.get(node.node_id, QVector3D(0, 0, 0))
            entity = self._create_node_entity(node, position)
            self._node_entities[node.node_id] = entity

        # Create edge entities
        for edge in self._graph.get("edges", []):
            source_pos = self._positions.get(edge.get("source"))
            target_pos = self._positions.get(edge.get("target"))
            if source_pos and target_pos:
                self._edge_entities.append(
                    self._create_edge_entity(source_pos, target_pos, edge.get("type", ""))
                )

        # Update transition manager with current positions
        self._transition_manager.set_current_positions(self._positions)

    def _create_node_entity(self, node: _GraphNode, position: QVector3D) -> "Qt3DCore.QEntity":
        """Create a 3D entity for a graph node."""
        entity = Qt3DCore.QEntity(self._root_entity)
        transform = Qt3DCore.QTransform()
        transform.setTranslation(position)
        entity.addComponent(transform)

        # Store transform for animation
        entity.setProperty("node_transform", transform)

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
        elif node.node_type == "class":
            mesh = Qt3DExtras.QCuboidMesh()
            mesh.setXExtent(2.0)
            mesh.setYExtent(1.2)
            mesh.setZExtent(2.0)
            material_color = QColor(200, 120, 50)
        else:  # function, variable
            mesh = Qt3DExtras.QSphereMesh()
            mesh.setRadius(1.0)
            material_color = QColor(220, 140, 70)

        # Use QPhongAlphaMaterial for opacity support
        material = Qt3DExtras.QPhongAlphaMaterial(entity)
        material.setDiffuse(material_color)
        material.setAlpha(1.0)
        self._node_materials[node.node_id] = material

        picker = Qt3DRender.QObjectPicker(entity)
        picker.setHoverEnabled(True)
        picker.clicked.connect(lambda _event, nid=node.node_id: self.node_clicked.emit(nid))
        picker.entered.connect(lambda nid=node.node_id: self.node_hovered.emit(nid))

        entity.addComponent(mesh)
        entity.addComponent(material)
        entity.addComponent(picker)
        return entity

    def _create_edge_entity(
        self,
        source: QVector3D,
        target: QVector3D,
        relation: str,
    ) -> "Qt3DCore.QEntity":
        """Create a 3D entity for a graph edge."""
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
        elif relation == "calls":
            material.setDiffuse(QColor(230, 90, 90))
        elif relation == "imports":
            material.setDiffuse(QColor(180, 100, 200))
        else:
            material.setDiffuse(QColor(200, 200, 200))

        self._edge_materials.append(material)

        entity.addComponent(mesh)
        entity.addComponent(transform)
        entity.addComponent(material)
        return entity

    # --- Animation helpers ---

    def _animate_to_positions(
        self,
        old_positions: Dict[str, QVector3D],
        new_positions: Dict[str, QVector3D],
    ) -> None:
        """Animate nodes from old positions to new positions."""
        self._transition_manager.set_current_positions(old_positions)
        self._transition_manager.animate_to_positions(
            new_positions,
            on_update=self._apply_positions,
            on_complete=self._on_animation_complete,
        )

    def _apply_positions(self, positions: Dict[str, QVector3D]) -> None:
        """Apply animated positions to nodes."""
        self._positions = positions
        self._update_node_positions()

    def _update_node_positions(self) -> None:
        """Update node transforms from current positions."""
        if not QT3D_AVAILABLE:
            return

        for node_id, position in self._positions.items():
            entity = self._node_entities.get(node_id)
            if entity:
                transform = entity.property("node_transform")
                if transform:
                    transform.setTranslation(position)

    def _update_camera(self, position: QVector3D, center: QVector3D) -> None:
        """Update camera position during animation."""
        if not QT3D_AVAILABLE:
            return

        camera = self._window.camera()
        camera.setPosition(position)
        camera.setViewCenter(center)

    def _on_animation_complete(self) -> None:
        """Handle animation completion."""
        self.animation_finished.emit()

    # --- Visibility callbacks ---

    def _on_visibility_changed(self, visibility: Dict[str, NodeVisibility]) -> None:
        """Handle visibility changes from focus manager."""
        if not QT3D_AVAILABLE:
            # For fallback renderer, filter the graph
            if self._fallback_renderer and self._graph:
                filtered = filter_graph_by_visibility(self._graph, visibility)
                self._fallback_renderer.set_graph(filtered)
            return

        # Update node materials for Qt3D
        for node_id, vis in visibility.items():
            material = self._node_materials.get(node_id)
            if material:
                material.setAlpha(vis.opacity)

            entity = self._node_entities.get(node_id)
            if entity:
                entity.setEnabled(vis.visible)

    # --- Legacy compatibility ---

    def _compute_positions(
        self,
        nodes: Iterable[_GraphNode],
        edges: List[dict],
    ) -> Dict[str, QVector3D]:
        """Compute positions using current layout algorithm.

        This method is kept for compatibility but delegates to layout_algorithms.
        """
        return compute_graph_layout(
            [
                {
                    "id": n.node_id,
                    "type": n.node_type,
                    "label": n.label,
                }
                for n in nodes
            ],
            edges,
            self._current_layout,
            self._layout_config,
        )
