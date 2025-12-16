"""Layout algorithms for positioning nodes in 2D/3D graph visualization.

This module provides various layout strategies for arranging graph nodes:
- Force-directed: Physics simulation for organic layouts
- Hierarchical: Tree-like layouts respecting containment
- Radial: Circular arrangement around central nodes
- Grid: Simple grid-based layout
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from PySide6.QtGui import QVector3D


class LayoutType(Enum):
    """Available layout algorithm types."""

    FORCE_DIRECTED = "force_directed"
    HIERARCHICAL = "hierarchical"
    RADIAL = "radial"
    GRID = "grid"
    CIRCULAR = "circular"


@dataclass
class LayoutNode:
    """A node with position data for layout calculations."""

    node_id: str
    node_type: str
    label: str
    position: QVector3D = field(default_factory=lambda: QVector3D(0, 0, 0))
    velocity: QVector3D = field(default_factory=lambda: QVector3D(0, 0, 0))
    fixed: bool = False
    parent_id: Optional[str] = None
    depth: int = 0

    # Visual properties
    mass: float = 1.0
    size: float = 1.0


@dataclass
class LayoutEdge:
    """An edge connecting two layout nodes."""

    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0


@dataclass
class LayoutConfig:
    """Configuration for layout algorithms."""

    # Force-directed settings
    repulsion_strength: float = 500.0
    attraction_strength: float = 0.1
    damping: float = 0.8
    max_iterations: int = 100
    convergence_threshold: float = 0.01

    # Hierarchical settings
    level_spacing: float = 8.0
    sibling_spacing: float = 5.0

    # Radial settings
    ring_spacing: float = 10.0
    angle_spread: float = 2 * math.pi

    # Grid settings
    grid_spacing: float = 6.0

    # 3D settings
    use_3d: bool = True
    z_layer_spacing: float = 5.0


class LayoutEngine:
    """Engine for computing graph layouts using various algorithms."""

    def __init__(self, config: Optional[LayoutConfig] = None) -> None:
        self.config = config or LayoutConfig()
        self._nodes: Dict[str, LayoutNode] = {}
        self._edges: List[LayoutEdge] = []
        self._children_map: Dict[str, List[str]] = {}

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        self._children_map.clear()

    def add_node(self, node: LayoutNode) -> None:
        """Add a node to the layout."""
        self._nodes[node.node_id] = node
        if node.parent_id:
            self._children_map.setdefault(node.parent_id, []).append(node.node_id)

    def add_edge(self, edge: LayoutEdge) -> None:
        """Add an edge to the layout."""
        self._edges.append(edge)

    def get_positions(self) -> Dict[str, QVector3D]:
        """Return current positions of all nodes."""
        return {node_id: node.position for node_id, node in self._nodes.items()}

    def compute_layout(self, layout_type: LayoutType) -> Dict[str, QVector3D]:
        """Compute node positions using the specified layout algorithm."""
        if layout_type == LayoutType.FORCE_DIRECTED:
            self._compute_force_directed()
        elif layout_type == LayoutType.HIERARCHICAL:
            self._compute_hierarchical()
        elif layout_type == LayoutType.RADIAL:
            self._compute_radial()
        elif layout_type == LayoutType.GRID:
            self._compute_grid()
        elif layout_type == LayoutType.CIRCULAR:
            self._compute_circular()
        else:
            self._compute_force_directed()

        return self.get_positions()

    # --- Force-directed layout ---

    def _compute_force_directed(self) -> None:
        """Apply force-directed (Fruchterman-Reingold style) layout."""
        if not self._nodes:
            return

        # Initialize positions randomly if not set
        self._initialize_positions()

        for iteration in range(self.config.max_iterations):
            total_displacement = 0.0
            forces: Dict[str, QVector3D] = {nid: QVector3D(0, 0, 0) for nid in self._nodes}

            # Calculate repulsive forces between all pairs
            node_ids = list(self._nodes.keys())
            for i, nid1 in enumerate(node_ids):
                for nid2 in node_ids[i + 1:]:
                    node1 = self._nodes[nid1]
                    node2 = self._nodes[nid2]

                    delta = node1.position - node2.position
                    distance = delta.length()
                    if distance < 0.01:
                        # Avoid division by zero - add small random offset
                        delta = QVector3D(random.uniform(-0.1, 0.1),
                                         random.uniform(-0.1, 0.1),
                                         random.uniform(-0.1, 0.1) if self.config.use_3d else 0)
                        distance = delta.length()

                    # Repulsive force (inversely proportional to distance squared)
                    repulsion = (self.config.repulsion_strength * node1.mass * node2.mass) / (distance * distance)
                    force = delta.normalized() * repulsion

                    forces[nid1] += force
                    forces[nid2] -= force

            # Calculate attractive forces along edges
            for edge in self._edges:
                if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
                    continue

                source = self._nodes[edge.source_id]
                target = self._nodes[edge.target_id]

                delta = target.position - source.position
                distance = delta.length()
                if distance < 0.01:
                    continue

                # Attractive force (proportional to distance)
                attraction = self.config.attraction_strength * distance * edge.weight
                force = delta.normalized() * attraction

                forces[edge.source_id] += force
                forces[edge.target_id] -= force

            # Apply forces with damping
            for nid, node in self._nodes.items():
                if node.fixed:
                    continue

                force = forces[nid]
                node.velocity = (node.velocity + force / node.mass) * self.config.damping
                displacement = node.velocity

                # Limit max displacement per iteration
                max_displacement = 5.0
                if displacement.length() > max_displacement:
                    displacement = displacement.normalized() * max_displacement

                node.position += displacement
                total_displacement += displacement.length()

            # Check convergence
            avg_displacement = total_displacement / len(self._nodes)
            if avg_displacement < self.config.convergence_threshold:
                break

        # Center the layout
        self._center_layout()

    # --- Hierarchical layout ---

    def _compute_hierarchical(self) -> None:
        """Compute hierarchical tree-like layout based on containment."""
        if not self._nodes:
            return

        # Build hierarchy from edges
        self._build_hierarchy_from_edges()

        # Find root nodes (nodes with no parent)
        root_nodes = [nid for nid, node in self._nodes.items() if not node.parent_id]
        if not root_nodes:
            root_nodes = list(self._nodes.keys())[:1]  # Pick first as root if no hierarchy

        # Assign depths
        self._assign_depths(root_nodes)

        # Position by depth level
        levels: Dict[int, List[str]] = {}
        for nid, node in self._nodes.items():
            levels.setdefault(node.depth, []).append(nid)

        for depth, node_ids in levels.items():
            y = -depth * self.config.level_spacing
            count = len(node_ids)

            for i, nid in enumerate(node_ids):
                x = (i - (count - 1) / 2) * self.config.sibling_spacing
                z = 0.0 if not self.config.use_3d else self._get_type_z_offset(self._nodes[nid].node_type)
                self._nodes[nid].position = QVector3D(x, y, z)

        self._center_layout()

    def _build_hierarchy_from_edges(self) -> None:
        """Build parent-child relationships from containment edges."""
        for edge in self._edges:
            if edge.edge_type == "contains":
                if edge.target_id in self._nodes:
                    self._nodes[edge.target_id].parent_id = edge.source_id
                    self._children_map.setdefault(edge.source_id, []).append(edge.target_id)

    def _assign_depths(self, root_ids: List[str], depth: int = 0) -> None:
        """Recursively assign depth values to nodes."""
        for nid in root_ids:
            if nid not in self._nodes:
                continue
            self._nodes[nid].depth = depth
            children = self._children_map.get(nid, [])
            self._assign_depths(children, depth + 1)

    # --- Radial layout ---

    def _compute_radial(self) -> None:
        """Compute radial layout with nodes in concentric rings by type."""
        if not self._nodes:
            return

        # Group nodes by type for different rings
        type_order = {"module": 0, "file": 1, "class": 2, "function": 3, "variable": 4}
        rings: Dict[int, List[str]] = {}

        for nid, node in self._nodes.items():
            ring_idx = type_order.get(node.node_type, 3)
            rings.setdefault(ring_idx, []).append(nid)

        for ring_idx, node_ids in rings.items():
            radius = (ring_idx + 1) * self.config.ring_spacing
            count = len(node_ids)
            if count == 0:
                continue

            angle_step = self.config.angle_spread / max(count, 1)

            for i, nid in enumerate(node_ids):
                angle = i * angle_step - self.config.angle_spread / 2
                x = radius * math.cos(angle)
                z = radius * math.sin(angle)
                y = 0.0 if not self.config.use_3d else ring_idx * self.config.z_layer_spacing * 0.5
                self._nodes[nid].position = QVector3D(x, y, z)

        self._center_layout()

    # --- Grid layout ---

    def _compute_grid(self) -> None:
        """Compute simple grid-based layout."""
        if not self._nodes:
            return

        node_ids = list(self._nodes.keys())
        count = len(node_ids)
        cols = max(1, int(math.ceil(math.sqrt(count))))

        for i, nid in enumerate(node_ids):
            row = i // cols
            col = i % cols
            x = col * self.config.grid_spacing
            z = row * self.config.grid_spacing
            y = 0.0 if not self.config.use_3d else self._get_type_z_offset(self._nodes[nid].node_type)
            self._nodes[nid].position = QVector3D(x, y, z)

        self._center_layout()

    # --- Circular layout ---

    def _compute_circular(self) -> None:
        """Compute circular layout with all nodes on a single circle."""
        if not self._nodes:
            return

        node_ids = list(self._nodes.keys())
        count = len(node_ids)
        if count == 0:
            return

        radius = max(10.0, count * self.config.grid_spacing / (2 * math.pi))
        angle_step = 2 * math.pi / count

        for i, nid in enumerate(node_ids):
            angle = i * angle_step
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            y = 0.0 if not self.config.use_3d else self._get_type_z_offset(self._nodes[nid].node_type)
            self._nodes[nid].position = QVector3D(x, y, z)

        self._center_layout()

    # --- Helper methods ---

    def _initialize_positions(self) -> None:
        """Initialize node positions randomly if not already set."""
        spread = 20.0
        for node in self._nodes.values():
            if node.position.isNull():
                node.position = QVector3D(
                    random.uniform(-spread, spread),
                    random.uniform(-spread, spread) if self.config.use_3d else 0,
                    random.uniform(-spread, spread)
                )

    def _center_layout(self) -> None:
        """Center the layout around origin."""
        if not self._nodes:
            return

        centroid = QVector3D(0, 0, 0)
        for node in self._nodes.values():
            centroid += node.position
        centroid /= len(self._nodes)

        for node in self._nodes.values():
            node.position -= centroid

    def _get_type_z_offset(self, node_type: str) -> float:
        """Get Z-axis offset based on node type for 3D layering."""
        offsets = {
            "module": 0.0,
            "file": -2.0,
            "class": -4.0,
            "function": -6.0,
            "variable": -8.0,
        }
        return offsets.get(node_type, -5.0)


def compute_graph_layout(
    nodes: Iterable[dict],
    edges: Iterable[dict],
    layout_type: LayoutType = LayoutType.FORCE_DIRECTED,
    config: Optional[LayoutConfig] = None,
) -> Dict[str, QVector3D]:
    """Convenience function to compute layout for a graph dictionary.

    Args:
        nodes: Iterable of node dictionaries with 'id', 'type', 'label' keys
        edges: Iterable of edge dictionaries with 'source', 'target', 'type' keys
        layout_type: The layout algorithm to use
        config: Optional layout configuration

    Returns:
        Dictionary mapping node IDs to QVector3D positions
    """
    engine = LayoutEngine(config)

    # Build containment hierarchy
    contains_map: Dict[str, str] = {}
    for edge in edges:
        if edge.get("type") == "contains":
            contains_map[edge.get("target", "")] = edge.get("source", "")

    # Add nodes with hierarchy info
    for node_dict in nodes:
        node_id = node_dict.get("id", "")
        node_type = node_dict.get("type", "unknown")

        # Set mass/size based on type
        mass = {"module": 3.0, "file": 2.0, "class": 1.5}.get(node_type, 1.0)

        layout_node = LayoutNode(
            node_id=node_id,
            node_type=node_type,
            label=node_dict.get("label", ""),
            parent_id=contains_map.get(node_id),
            mass=mass,
        )
        engine.add_node(layout_node)

    # Add edges
    for edge_dict in edges:
        edge = LayoutEdge(
            source_id=edge_dict.get("source", ""),
            target_id=edge_dict.get("target", ""),
            edge_type=edge_dict.get("type", ""),
            weight=1.0 if edge_dict.get("type") != "contains" else 2.0,
        )
        engine.add_edge(edge)

    return engine.compute_layout(layout_type)
