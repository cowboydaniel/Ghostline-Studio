"""OpenGL fallback renderer for 3D architecture visualization.

This module provides an alternative rendering path using OpenGL when Qt3D
is not available. It renders a 2D/2.5D representation of the architecture graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from ghostline.visual3d.layout_algorithms import LayoutConfig, LayoutType, compute_graph_layout


@dataclass
class FallbackNode:
    """Node representation for fallback renderer."""

    node_id: str
    node_type: str
    label: str
    file: Optional[str]
    line: Optional[int]
    x: float
    y: float
    width: float
    height: float
    color: QColor
    hovered: bool = False


@dataclass
class FallbackEdge:
    """Edge representation for fallback renderer."""

    source_id: str
    target_id: str
    edge_type: str
    color: QColor


class FallbackRenderer(QWidget):
    """2D fallback renderer using QPainter when Qt3D is unavailable.

    Features:
    - Pan and zoom navigation
    - Clickable nodes
    - Hover highlighting
    - Smooth antialiased rendering
    """

    node_clicked = Signal(str)
    node_hovered = Signal(str)

    # Node type colors
    NODE_COLORS = {
        "module": QColor(0, 122, 204),       # Blue
        "file": QColor(70, 180, 130),         # Green
        "class": QColor(200, 120, 50),        # Orange
        "function": QColor(220, 140, 70),     # Light orange
        "variable": QColor(150, 150, 150),    # Gray
    }

    # Node type sizes
    NODE_SIZES = {
        "module": (80, 40),
        "file": (60, 30),
        "class": (50, 25),
        "function": (40, 20),
        "variable": (30, 15),
    }

    EDGE_COLORS = {
        "contains": QColor(160, 160, 160, 150),
        "calls": QColor(230, 90, 90, 200),
        "imports": QColor(180, 100, 200, 200),
        "defines": QColor(100, 180, 100, 180),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400, 300)

        self._nodes: Dict[str, FallbackNode] = {}
        self._edges: List[FallbackEdge] = []
        self._graph: dict | None = None

        # View transform state
        self._pan_offset = QPointF(0, 0)
        self._zoom_level = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 5.0

        # Interaction state
        self._dragging = False
        self._last_mouse_pos: Optional[QPoint] = None
        self._hovered_node: Optional[str] = None

        # Layout settings
        self._layout_type = LayoutType.HIERARCHICAL
        self._layout_config = LayoutConfig(use_3d=False)

        # Animation state (for smooth transitions)
        self._animation_progress = 1.0

    # --- Public API ---

    def set_graph(self, graph: dict | None) -> None:
        """Set the graph data and compute layout."""
        self._graph = graph or {"nodes": [], "edges": []}
        self._build_scene()
        self.update()

    def set_layout(self, layout_type: LayoutType) -> None:
        """Change the layout algorithm and recompute positions."""
        self._layout_type = layout_type
        self._build_scene()
        self.update()

    def reset_view(self) -> None:
        """Reset pan and zoom to default."""
        self._pan_offset = QPointF(0, 0)
        self._zoom_level = 1.0
        self._fit_to_view()
        self.update()

    def center_on_node(self, node_id: str) -> None:
        """Center the view on a specific node."""
        if node_id not in self._nodes:
            return
        node = self._nodes[node_id]
        center = QPointF(self.width() / 2, self.height() / 2)
        node_center = QPointF(node.x + node.width / 2, node.y + node.height / 2)
        self._pan_offset = center - node_center * self._zoom_level
        self.update()

    def zoom_to_fit(self) -> None:
        """Fit all nodes in the view."""
        self._fit_to_view()
        self.update()

    @property
    def render_available(self) -> bool:
        """Always available as fallback."""
        return bool(self._nodes)

    # --- Scene building ---

    def _build_scene(self) -> None:
        """Build renderable nodes and edges from graph data."""
        self._nodes.clear()
        self._edges.clear()

        if not self._graph:
            return

        nodes_data = self._graph.get("nodes", [])
        edges_data = self._graph.get("edges", [])

        if not nodes_data:
            return

        # Compute layout positions
        positions = compute_graph_layout(
            nodes_data,
            edges_data,
            self._layout_type,
            self._layout_config,
        )

        # Create renderable nodes
        for node_dict in nodes_data:
            node_id = node_dict.get("id", "")
            node_type = node_dict.get("type", "unknown")
            pos = positions.get(node_id)
            if not pos:
                continue

            width, height = self.NODE_SIZES.get(node_type, (40, 20))
            color = self.NODE_COLORS.get(node_type, QColor(128, 128, 128))

            # Scale position for screen coordinates
            scale = 10.0  # Convert from layout units to pixels
            self._nodes[node_id] = FallbackNode(
                node_id=node_id,
                node_type=node_type,
                label=node_dict.get("label", ""),
                file=node_dict.get("file"),
                line=node_dict.get("line"),
                x=pos.x() * scale,
                y=pos.z() * scale,  # Use Z as Y for 2D
                width=width,
                height=height,
                color=color,
            )

        # Create renderable edges
        for edge_dict in edges_data:
            source_id = edge_dict.get("source", "")
            target_id = edge_dict.get("target", "")
            edge_type = edge_dict.get("type", "")

            if source_id not in self._nodes or target_id not in self._nodes:
                continue

            color = self.EDGE_COLORS.get(edge_type, QColor(128, 128, 128, 150))
            self._edges.append(FallbackEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                color=color,
            ))

        self._fit_to_view()

    def _fit_to_view(self) -> None:
        """Adjust zoom and pan to fit all nodes."""
        if not self._nodes:
            return

        # Calculate bounding box
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for node in self._nodes.values():
            min_x = min(min_x, node.x)
            min_y = min(min_y, node.y)
            max_x = max(max_x, node.x + node.width)
            max_y = max(max_y, node.y + node.height)

        if min_x == float("inf"):
            return

        # Add padding
        padding = 50
        width = max_x - min_x + padding * 2
        height = max_y - min_y + padding * 2

        # Calculate zoom to fit
        view_width = max(self.width(), 100)
        view_height = max(self.height(), 100)

        zoom_x = view_width / width if width > 0 else 1.0
        zoom_y = view_height / height if height > 0 else 1.0
        self._zoom_level = min(zoom_x, zoom_y, 2.0)  # Cap at 2x zoom
        self._zoom_level = max(self._zoom_level, self._min_zoom)

        # Center the content
        content_center_x = (min_x + max_x) / 2
        content_center_y = (min_y + max_y) / 2
        view_center = QPointF(view_width / 2, view_height / 2)

        self._pan_offset = view_center - QPointF(content_center_x, content_center_y) * self._zoom_level

    # --- Painting ---

    def paintEvent(self, event) -> None:
        """Render the graph visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(30, 30, 35))

        if not self._nodes:
            self._draw_placeholder(painter)
            return

        # Apply view transform
        painter.translate(self._pan_offset)
        painter.scale(self._zoom_level, self._zoom_level)

        # Draw grid (optional decorative element)
        self._draw_grid(painter)

        # Draw edges first (behind nodes)
        for edge in self._edges:
            self._draw_edge(painter, edge)

        # Draw nodes on top
        for node in self._nodes.values():
            self._draw_node(painter, node)

        painter.end()

    def _draw_placeholder(self, painter: QPainter) -> None:
        """Draw placeholder text when no graph is loaded."""
        painter.setPen(QColor(150, 150, 150))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "No architecture data available.\nOpen a workspace to visualize the codebase structure.",
        )

    def _draw_grid(self, painter: QPainter) -> None:
        """Draw a subtle grid pattern."""
        grid_size = 50
        pen = QPen(QColor(50, 50, 55))
        pen.setWidth(1)
        painter.setPen(pen)

        # Calculate visible area in scene coordinates
        visible_rect = self._get_visible_rect()

        start_x = int(visible_rect.left() / grid_size) * grid_size
        start_y = int(visible_rect.top() / grid_size) * grid_size
        end_x = int(visible_rect.right() / grid_size + 1) * grid_size
        end_y = int(visible_rect.bottom() / grid_size + 1) * grid_size

        for x in range(start_x, end_x, grid_size):
            painter.drawLine(x, start_y, x, end_y)
        for y in range(start_y, end_y, grid_size):
            painter.drawLine(start_x, y, end_x, y)

    def _draw_node(self, painter: QPainter, node: FallbackNode) -> None:
        """Draw a single node with styling."""
        rect = QRectF(node.x, node.y, node.width, node.height)

        # Create gradient fill
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        base_color = node.color
        if node.hovered or node.node_id == self._hovered_node:
            base_color = base_color.lighter(130)

        gradient.setColorAt(0, base_color.lighter(120))
        gradient.setColorAt(1, base_color)

        # Draw shadow
        shadow_rect = rect.translated(2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 40))
        if node.node_type == "function":
            painter.drawEllipse(shadow_rect)
        else:
            painter.drawRoundedRect(shadow_rect, 4, 4)

        # Draw node shape
        painter.setBrush(gradient)
        pen = QPen(base_color.darker(150))
        pen.setWidth(2 if node.hovered else 1)
        painter.setPen(pen)

        if node.node_type == "function":
            painter.drawEllipse(rect)
        else:
            painter.drawRoundedRect(rect, 4, 4)

        # Draw label
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(max(7, int(8 * min(node.width / 40, 1.5))))
        painter.setFont(font)

        # Truncate label if too long
        metrics = QFontMetrics(font)
        label = node.label
        max_width = int(node.width - 8)
        if metrics.horizontalAdvance(label) > max_width:
            label = metrics.elidedText(label, Qt.ElideMiddle, max_width)

        painter.drawText(rect, Qt.AlignCenter, label)

    def _draw_edge(self, painter: QPainter, edge: FallbackEdge) -> None:
        """Draw an edge between two nodes."""
        source = self._nodes.get(edge.source_id)
        target = self._nodes.get(edge.target_id)
        if not source or not target:
            return

        # Calculate connection points (center of nodes)
        source_center = QPointF(source.x + source.width / 2, source.y + source.height / 2)
        target_center = QPointF(target.x + target.width / 2, target.y + target.height / 2)

        pen = QPen(edge.color)
        pen.setWidth(2 if edge.edge_type != "contains" else 1)
        if edge.edge_type == "contains":
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)

        # Draw curved bezier path for non-containment edges
        if edge.edge_type != "contains":
            path = QPainterPath()
            path.moveTo(source_center)

            # Calculate control points for curve
            mid_x = (source_center.x() + target_center.x()) / 2
            mid_y = (source_center.y() + target_center.y()) / 2
            dx = target_center.x() - source_center.x()
            dy = target_center.y() - source_center.y()

            # Perpendicular offset for curve
            offset = min(abs(dx), abs(dy)) * 0.3
            ctrl_x = mid_x - dy * 0.1
            ctrl_y = mid_y + dx * 0.1

            path.quadTo(QPointF(ctrl_x, ctrl_y), target_center)
            painter.drawPath(path)

            # Draw arrow head
            self._draw_arrow(painter, QPointF(ctrl_x, ctrl_y), target_center, edge.color)
        else:
            painter.drawLine(source_center, target_center)

    def _draw_arrow(self, painter: QPainter, from_point: QPointF, to_point: QPointF, color: QColor) -> None:
        """Draw an arrow head at the target end of an edge."""
        arrow_size = 8
        dx = to_point.x() - from_point.x()
        dy = to_point.y() - from_point.y()
        angle = math.atan2(dy, dx)

        p1 = QPointF(
            to_point.x() - arrow_size * math.cos(angle - math.pi / 6),
            to_point.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            to_point.x() - arrow_size * math.cos(angle + math.pi / 6),
            to_point.y() - arrow_size * math.sin(angle + math.pi / 6),
        )

        path = QPainterPath()
        path.moveTo(to_point)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def _get_visible_rect(self) -> QRectF:
        """Get the visible scene rectangle."""
        inv_transform = QTransform()
        inv_transform.scale(1 / self._zoom_level, 1 / self._zoom_level)
        inv_transform.translate(-self._pan_offset.x() / self._zoom_level,
                               -self._pan_offset.y() / self._zoom_level)
        return inv_transform.mapRect(QRectF(self.rect()))

    # --- Mouse interaction ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for node clicks and pan start."""
        if event.button() == Qt.LeftButton:
            scene_pos = self._screen_to_scene(event.position())
            clicked_node = self._node_at(scene_pos)

            if clicked_node:
                self.node_clicked.emit(clicked_node)
            else:
                self._dragging = True
                self._last_mouse_pos = event.position().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._last_mouse_pos = None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for panning and hover detection."""
        if self._dragging and self._last_mouse_pos:
            delta = event.position().toPoint() - self._last_mouse_pos
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._last_mouse_pos = event.position().toPoint()
            self.update()
        else:
            # Hover detection
            scene_pos = self._screen_to_scene(event.position())
            hovered = self._node_at(scene_pos)
            if hovered != self._hovered_node:
                self._hovered_node = hovered
                if hovered:
                    self.node_hovered.emit(hovered)
                self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        zoom_factor = 1.15
        old_zoom = self._zoom_level

        if event.angleDelta().y() > 0:
            self._zoom_level = min(self._zoom_level * zoom_factor, self._max_zoom)
        else:
            self._zoom_level = max(self._zoom_level / zoom_factor, self._min_zoom)

        # Zoom toward mouse position
        mouse_pos = event.position()
        scale_change = self._zoom_level / old_zoom
        self._pan_offset = mouse_pos - (mouse_pos - self._pan_offset) * scale_change

        self.update()

    def _screen_to_scene(self, screen_pos: QPointF) -> QPointF:
        """Convert screen coordinates to scene coordinates."""
        return QPointF(
            (screen_pos.x() - self._pan_offset.x()) / self._zoom_level,
            (screen_pos.y() - self._pan_offset.y()) / self._zoom_level,
        )

    def _node_at(self, scene_pos: QPointF) -> Optional[str]:
        """Find node at scene position."""
        for node_id, node in self._nodes.items():
            rect = QRectF(node.x, node.y, node.width, node.height)
            if rect.contains(scene_pos):
                return node_id
        return None

    # --- Export ---

    def grab_image(self) -> "QPixmap":
        """Capture the current view as an image."""
        from PySide6.QtGui import QPixmap
        return self.grab()

    def export_to_file(self, file_path: str) -> bool:
        """Export the visualization to an image file."""
        pixmap = self.grab_image()
        return pixmap.save(file_path)
