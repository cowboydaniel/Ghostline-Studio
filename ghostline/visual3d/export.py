"""Export functionality for 3D visualization.

This module provides export capabilities:
- Export to PNG/JPEG/BMP images
- Export to SVG (vector graphics)
- Export to JSON (graph data)
- High-resolution export
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QPixmap


class ExportFormat(Enum):
    """Supported export formats."""

    PNG = "png"
    JPEG = "jpeg"
    BMP = "bmp"
    SVG = "svg"
    JSON = "json"


@dataclass
class ExportConfig:
    """Configuration for export operations."""

    format: ExportFormat = ExportFormat.PNG
    width: int = 1920
    height: int = 1080
    scale_factor: float = 1.0
    background_color: QColor = field(default_factory=lambda: QColor(30, 30, 35))
    include_legend: bool = True
    include_title: bool = True
    title: str = "Architecture Visualization"
    quality: int = 95  # For JPEG


class ExportManager:
    """Manager for exporting visualizations to various formats."""

    NODE_COLORS = {
        "module": QColor(0, 122, 204),
        "file": QColor(70, 180, 130),
        "class": QColor(200, 120, 50),
        "function": QColor(220, 140, 70),
        "variable": QColor(150, 150, 150),
    }

    def __init__(self, config: Optional[ExportConfig] = None) -> None:
        self._config = config or ExportConfig()
        self._graph: dict | None = None
        self._positions: Dict[str, tuple[float, float]] = {}

    def set_config(self, config: ExportConfig) -> None:
        """Update export configuration."""
        self._config = config

    def set_graph_data(
        self,
        graph: dict,
        positions: Dict[str, tuple[float, float]],
    ) -> None:
        """Set graph data for export.

        Args:
            graph: Graph dict with nodes and edges
            positions: Dict mapping node ID to (x, y) position
        """
        self._graph = graph
        self._positions = positions

    # --- Export methods ---

    def export_to_file(
        self,
        file_path: str | Path,
        widget: Optional[QWidget] = None,
    ) -> bool:
        """Export visualization to a file.

        Args:
            file_path: Output file path
            widget: Optional widget to capture (for raster formats)

        Returns:
            True if export succeeded
        """
        path = Path(file_path)
        suffix = path.suffix.lower().lstrip(".")

        # Determine format from extension
        format_map = {
            "png": ExportFormat.PNG,
            "jpg": ExportFormat.JPEG,
            "jpeg": ExportFormat.JPEG,
            "bmp": ExportFormat.BMP,
            "svg": ExportFormat.SVG,
            "json": ExportFormat.JSON,
        }
        export_format = format_map.get(suffix, self._config.format)

        if export_format == ExportFormat.JSON:
            return self._export_json(path)
        elif export_format == ExportFormat.SVG:
            return self._export_svg(path)
        elif widget:
            return self._export_raster_from_widget(path, widget, export_format)
        else:
            return self._export_raster_generated(path, export_format)

    def export_dialog(
        self,
        parent: QWidget,
        widget: Optional[QWidget] = None,
    ) -> Optional[str]:
        """Show export dialog and export if user confirms.

        Args:
            parent: Parent widget for dialog
            widget: Optional widget to capture

        Returns:
            Export file path if succeeded, None otherwise
        """
        file_filter = (
            "PNG Image (*.png);;"
            "JPEG Image (*.jpg *.jpeg);;"
            "BMP Image (*.bmp);;"
            "SVG Vector (*.svg);;"
            "JSON Data (*.json)"
        )

        file_path, selected_filter = QFileDialog.getSaveFileName(
            parent,
            "Export Visualization",
            f"architecture_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            file_filter,
        )

        if not file_path:
            return None

        # Ensure extension
        if not Path(file_path).suffix:
            if "PNG" in selected_filter:
                file_path += ".png"
            elif "JPEG" in selected_filter or "JPG" in selected_filter:
                file_path += ".jpg"
            elif "BMP" in selected_filter:
                file_path += ".bmp"
            elif "SVG" in selected_filter:
                file_path += ".svg"
            elif "JSON" in selected_filter:
                file_path += ".json"

        success = self.export_to_file(file_path, widget)

        if success:
            QMessageBox.information(
                parent,
                "Export Successful",
                f"Visualization exported to:\n{file_path}",
            )
            return file_path
        else:
            QMessageBox.warning(
                parent,
                "Export Failed",
                "Failed to export visualization. Please try again.",
            )
            return None

    # --- Raster export ---

    def _export_raster_from_widget(
        self,
        path: Path,
        widget: QWidget,
        export_format: ExportFormat,
    ) -> bool:
        """Export by capturing widget contents."""
        # High-DPI export
        scale = self._config.scale_factor
        size = QSize(
            int(self._config.width * scale),
            int(self._config.height * scale),
        )

        pixmap = widget.grab(widget.rect())
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            format_str = export_format.value.upper()
            if format_str == "JPEG":
                return scaled.save(str(path), "JPEG", self._config.quality)
            return scaled.save(str(path), format_str)

        return False

    def _export_raster_generated(
        self,
        path: Path,
        export_format: ExportFormat,
    ) -> bool:
        """Generate raster image from graph data."""
        if not self._graph or not self._positions:
            return False

        scale = self._config.scale_factor
        width = int(self._config.width * scale)
        height = int(self._config.height * scale)

        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(self._config.background_color)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        self._draw_graph(painter, width, height)

        if self._config.include_title:
            self._draw_title(painter, width)

        if self._config.include_legend:
            self._draw_legend(painter, width, height)

        painter.end()

        format_str = export_format.value.upper()
        if format_str == "JPEG":
            return image.save(str(path), "JPEG", self._config.quality)
        return image.save(str(path), format_str)

    def _draw_graph(
        self,
        painter: QPainter,
        width: int,
        height: int,
    ) -> None:
        """Draw graph nodes and edges."""
        if not self._graph:
            return

        # Calculate scale and offset to fit
        if not self._positions:
            return

        min_x = min(pos[0] for pos in self._positions.values())
        max_x = max(pos[0] for pos in self._positions.values())
        min_y = min(pos[1] for pos in self._positions.values())
        max_y = max(pos[1] for pos in self._positions.values())

        padding = 100
        graph_width = max_x - min_x or 1
        graph_height = max_y - min_y or 1

        scale_x = (width - padding * 2) / graph_width
        scale_y = (height - padding * 2) / graph_height
        scale = min(scale_x, scale_y, 5.0)

        offset_x = (width - graph_width * scale) / 2 - min_x * scale
        offset_y = (height - graph_height * scale) / 2 - min_y * scale

        def transform(pos: tuple[float, float]) -> tuple[float, float]:
            return (pos[0] * scale + offset_x, pos[1] * scale + offset_y)

        # Draw edges first
        for edge in self._graph.get("edges", []):
            source_id = edge.get("source", "")
            target_id = edge.get("target", "")
            edge_type = edge.get("type", "")

            if source_id not in self._positions or target_id not in self._positions:
                continue

            source_pos = transform(self._positions[source_id])
            target_pos = transform(self._positions[target_id])

            pen = QPen()
            if edge_type == "contains":
                pen.setColor(QColor(160, 160, 160, 150))
                pen.setWidth(1)
                pen.setStyle(Qt.DashLine)
            else:
                pen.setColor(QColor(230, 90, 90, 200))
                pen.setWidth(2)

            painter.setPen(pen)
            painter.drawLine(
                int(source_pos[0]), int(source_pos[1]),
                int(target_pos[0]), int(target_pos[1]),
            )

        # Draw nodes
        for node in self._graph.get("nodes", []):
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("label", "")

            if node_id not in self._positions:
                continue

            pos = transform(self._positions[node_id])
            color = self.NODE_COLORS.get(node_type, QColor(128, 128, 128))

            # Size based on type
            sizes = {
                "module": (80, 40),
                "file": (60, 30),
                "class": (50, 25),
                "function": (40, 20),
                "variable": (30, 15),
            }
            size = sizes.get(node_type, (40, 20))

            # Draw node
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(150), 2))

            x = int(pos[0] - size[0] / 2)
            y = int(pos[1] - size[1] / 2)

            if node_type == "function":
                painter.drawEllipse(x, y, size[0], size[1])
            else:
                painter.drawRoundedRect(x, y, size[0], size[1], 4, 4)

            # Draw label
            painter.setPen(QColor(255, 255, 255))
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)

            metrics = QFontMetrics(font)
            elided = metrics.elidedText(label, Qt.ElideMiddle, size[0] - 4)
            text_rect = metrics.boundingRect(elided)
            painter.drawText(
                int(pos[0] - text_rect.width() / 2),
                int(pos[1] + text_rect.height() / 4),
                elided,
            )

    def _draw_title(self, painter: QPainter, width: int) -> None:
        """Draw title at top of image."""
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(20, 35, self._config.title)

        # Subtitle with timestamp
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(180, 180, 180))
        painter.drawText(20, 55, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    def _draw_legend(self, painter: QPainter, width: int, height: int) -> None:
        """Draw legend showing node types."""
        legend_x = width - 150
        legend_y = height - 150
        item_height = 22

        painter.setPen(QColor(200, 200, 200))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        painter.drawText(legend_x, legend_y, "Legend:")
        legend_y += item_height

        items = [
            ("Module", "module"),
            ("File", "file"),
            ("Class", "class"),
            ("Function", "function"),
        ]

        for label, node_type in items:
            color = self.NODE_COLORS.get(node_type, QColor(128, 128, 128))
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(150), 1))

            painter.drawRoundedRect(legend_x, legend_y - 12, 16, 14, 2, 2)

            painter.setPen(QColor(200, 200, 200))
            painter.drawText(legend_x + 22, legend_y, label)
            legend_y += item_height

    # --- SVG export ---

    def _export_svg(self, path: Path) -> bool:
        """Export to SVG vector format."""
        if not self._graph or not self._positions:
            return False

        width = self._config.width
        height = self._config.height

        # Calculate transform
        if not self._positions:
            return False

        min_x = min(pos[0] for pos in self._positions.values())
        max_x = max(pos[0] for pos in self._positions.values())
        min_y = min(pos[1] for pos in self._positions.values())
        max_y = max(pos[1] for pos in self._positions.values())

        padding = 100
        graph_width = max_x - min_x or 1
        graph_height = max_y - min_y or 1

        scale_x = (width - padding * 2) / graph_width
        scale_y = (height - padding * 2) / graph_height
        scale = min(scale_x, scale_y, 5.0)

        offset_x = (width - graph_width * scale) / 2 - min_x * scale
        offset_y = (height - graph_height * scale) / 2 - min_y * scale

        def transform(pos: tuple[float, float]) -> tuple[float, float]:
            return (pos[0] * scale + offset_x, pos[1] * scale + offset_y)

        svg_lines: List[str] = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
            f'  <rect width="100%" height="100%" fill="#{self._config.background_color.name()[1:]}"/>',
        ]

        # Title
        if self._config.include_title:
            svg_lines.extend([
                f'  <text x="20" y="35" font-family="sans-serif" font-size="18" font-weight="bold" fill="white">{self._config.title}</text>',
                f'  <text x="20" y="55" font-family="sans-serif" font-size="10" fill="#b4b4b4">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</text>',
            ])

        # Edges
        svg_lines.append('  <g id="edges">')
        for edge in self._graph.get("edges", []):
            source_id = edge.get("source", "")
            target_id = edge.get("target", "")
            edge_type = edge.get("type", "")

            if source_id not in self._positions or target_id not in self._positions:
                continue

            source_pos = transform(self._positions[source_id])
            target_pos = transform(self._positions[target_id])

            stroke = "#a0a0a0" if edge_type == "contains" else "#e65a5a"
            stroke_width = 1 if edge_type == "contains" else 2
            dash = 'stroke-dasharray="5,3"' if edge_type == "contains" else ""

            svg_lines.append(
                f'    <line x1="{source_pos[0]:.1f}" y1="{source_pos[1]:.1f}" '
                f'x2="{target_pos[0]:.1f}" y2="{target_pos[1]:.1f}" '
                f'stroke="{stroke}" stroke-width="{stroke_width}" {dash} opacity="0.7"/>'
            )
        svg_lines.append('  </g>')

        # Nodes
        svg_lines.append('  <g id="nodes">')
        for node in self._graph.get("nodes", []):
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("label", "")

            if node_id not in self._positions:
                continue

            pos = transform(self._positions[node_id])
            color = self.NODE_COLORS.get(node_type, QColor(128, 128, 128))
            color_hex = f"#{color.name()[1:]}"

            sizes = {
                "module": (80, 40),
                "file": (60, 30),
                "class": (50, 25),
                "function": (40, 20),
                "variable": (30, 15),
            }
            size = sizes.get(node_type, (40, 20))

            x = pos[0] - size[0] / 2
            y = pos[1] - size[1] / 2

            if node_type == "function":
                cx = pos[0]
                cy = pos[1]
                rx = size[0] / 2
                ry = size[1] / 2
                svg_lines.append(
                    f'    <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                    f'fill="{color_hex}" stroke="{color_hex}" stroke-width="1"/>'
                )
            else:
                svg_lines.append(
                    f'    <rect x="{x:.1f}" y="{y:.1f}" width="{size[0]}" height="{size[1]}" '
                    f'rx="4" fill="{color_hex}" stroke="{color_hex}" stroke-width="1"/>'
                )

            # Truncate label for SVG
            display_label = label[:12] + "..." if len(label) > 15 else label
            svg_lines.append(
                f'    <text x="{pos[0]:.1f}" y="{pos[1] + 4:.1f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="8" fill="white">{display_label}</text>'
            )

        svg_lines.append('  </g>')

        # Legend
        if self._config.include_legend:
            legend_x = width - 150
            legend_y = height - 150
            svg_lines.append('  <g id="legend">')
            svg_lines.append(f'    <text x="{legend_x}" y="{legend_y}" font-family="sans-serif" font-size="9" fill="#c8c8c8">Legend:</text>')

            items = [("Module", "module"), ("File", "file"), ("Class", "class"), ("Function", "function")]
            for i, (name, ntype) in enumerate(items):
                y = legend_y + 22 * (i + 1)
                color = self.NODE_COLORS.get(ntype, QColor(128, 128, 128))
                color_hex = f"#{color.name()[1:]}"
                svg_lines.append(f'    <rect x="{legend_x}" y="{y - 12}" width="16" height="14" rx="2" fill="{color_hex}"/>')
                svg_lines.append(f'    <text x="{legend_x + 22}" y="{y}" font-family="sans-serif" font-size="9" fill="#c8c8c8">{name}</text>')

            svg_lines.append('  </g>')

        svg_lines.append('</svg>')

        try:
            path.write_text("\n".join(svg_lines), encoding="utf-8")
            return True
        except OSError:
            return False

    # --- JSON export ---

    def _export_json(self, path: Path) -> bool:
        """Export graph data as JSON."""
        if not self._graph:
            return False

        export_data = {
            "metadata": {
                "title": self._config.title,
                "generated": datetime.now().isoformat(),
                "format_version": "1.0",
            },
            "graph": self._graph,
            "positions": {
                nid: {"x": pos[0], "y": pos[1]}
                for nid, pos in self._positions.items()
            },
        }

        try:
            path.write_text(
                json.dumps(export_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False


def quick_export_png(
    widget: QWidget,
    file_path: str | Path,
    scale: float = 1.0,
) -> bool:
    """Quick helper to export a widget to PNG.

    Args:
        widget: Widget to capture
        file_path: Output path
        scale: Scale factor for high-DPI export

    Returns:
        True if export succeeded
    """
    pixmap = widget.grab()
    if scale != 1.0:
        size = QSize(
            int(pixmap.width() * scale),
            int(pixmap.height() * scale),
        )
        pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    return pixmap.save(str(file_path), "PNG")
