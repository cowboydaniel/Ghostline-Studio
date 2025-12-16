"""Focus mode system for graph visualization filtering and isolation.

This module provides advanced filtering capabilities:
- Focus on specific nodes and their connections
- Isolate node clusters
- Filter by various criteria (type, depth, file)
- Highlight paths between nodes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, FrozenSet, List, Optional, Set

from PySide6.QtCore import QObject, Signal


class FocusLevel(Enum):
    """Level of focus isolation."""

    NONE = "none"                # Show all nodes
    HIGHLIGHT = "highlight"       # Highlight focused, dim others
    NEIGHBORS = "neighbors"       # Show focused + direct connections
    EXTENDED = "extended"         # Show focused + 2-hop connections
    ISOLATE = "isolate"          # Show only focused nodes


class FilterCriteria(Enum):
    """Available filter criteria."""

    ALL = "all"
    MODULES = "modules"
    FILES = "files"
    CLASSES = "classes"
    FUNCTIONS = "functions"
    VARIABLES = "variables"
    BY_FILE = "by_file"
    BY_DEPTH = "by_depth"
    CUSTOM = "custom"


@dataclass
class NodeVisibility:
    """Visibility state for a node."""

    node_id: str
    visible: bool = True
    highlighted: bool = False
    dimmed: bool = False
    opacity: float = 1.0


@dataclass
class FilterState:
    """Current filter configuration."""

    criteria: FilterCriteria = FilterCriteria.ALL
    focus_level: FocusLevel = FocusLevel.NONE
    focused_nodes: FrozenSet[str] = field(default_factory=frozenset)
    visible_types: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"module", "file", "class", "function", "variable"})
    )
    file_filter: Optional[str] = None
    max_depth: Optional[int] = None
    custom_predicate: Optional[Callable[[dict], bool]] = None


class FocusModeManager(QObject):
    """Manager for focus mode and filtering in graph visualization.

    Signals:
        visibility_changed: Emitted when node visibility changes
        filter_changed: Emitted when filter configuration changes
        focus_changed: Emitted when focus target changes
    """

    visibility_changed = Signal(dict)  # node_id -> NodeVisibility
    filter_changed = Signal(object)     # FilterState
    focus_changed = Signal(set)         # focused node IDs

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._graph: dict | None = None
        self._filter_state = FilterState()
        self._visibility: Dict[str, NodeVisibility] = {}

        # Adjacency cache for neighbor lookups
        self._adjacency: Dict[str, Set[str]] = {}
        self._reverse_adjacency: Dict[str, Set[str]] = {}

    # --- Graph data ---

    def set_graph(self, graph: dict | None) -> None:
        """Set the source graph data."""
        self._graph = graph or {"nodes": [], "edges": []}
        self._build_adjacency()
        self._update_visibility()

    def _build_adjacency(self) -> None:
        """Build adjacency maps for fast neighbor lookups."""
        self._adjacency.clear()
        self._reverse_adjacency.clear()

        if not self._graph:
            return

        for edge in self._graph.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")
            self._adjacency.setdefault(source, set()).add(target)
            self._reverse_adjacency.setdefault(target, set()).add(source)

    # --- Filter configuration ---

    def set_filter(self, criteria: FilterCriteria, **kwargs) -> None:
        """Set the filter criteria.

        Args:
            criteria: The filter type to apply
            **kwargs: Additional filter parameters:
                - visible_types: Set of node types to show
                - file_filter: File path substring to filter by
                - max_depth: Maximum hierarchy depth
                - custom_predicate: Custom filter function
        """
        visible_types = kwargs.get("visible_types")
        if visible_types is None:
            if criteria == FilterCriteria.MODULES:
                visible_types = frozenset({"module"})
            elif criteria == FilterCriteria.FILES:
                visible_types = frozenset({"file"})
            elif criteria == FilterCriteria.CLASSES:
                visible_types = frozenset({"class"})
            elif criteria == FilterCriteria.FUNCTIONS:
                visible_types = frozenset({"function"})
            elif criteria == FilterCriteria.VARIABLES:
                visible_types = frozenset({"variable"})
            else:
                visible_types = frozenset({"module", "file", "class", "function", "variable"})

        self._filter_state = FilterState(
            criteria=criteria,
            focus_level=self._filter_state.focus_level,
            focused_nodes=self._filter_state.focused_nodes,
            visible_types=frozenset(visible_types),
            file_filter=kwargs.get("file_filter"),
            max_depth=kwargs.get("max_depth"),
            custom_predicate=kwargs.get("custom_predicate"),
        )

        self._update_visibility()
        self.filter_changed.emit(self._filter_state)

    def set_visible_types(self, types: Set[str]) -> None:
        """Set which node types are visible."""
        self._filter_state = FilterState(
            criteria=self._filter_state.criteria,
            focus_level=self._filter_state.focus_level,
            focused_nodes=self._filter_state.focused_nodes,
            visible_types=frozenset(types),
            file_filter=self._filter_state.file_filter,
            max_depth=self._filter_state.max_depth,
            custom_predicate=self._filter_state.custom_predicate,
        )
        self._update_visibility()
        self.filter_changed.emit(self._filter_state)

    # --- Focus mode ---

    def focus_on(
        self,
        node_ids: Set[str],
        level: FocusLevel = FocusLevel.NEIGHBORS,
    ) -> None:
        """Focus on specific nodes.

        Args:
            node_ids: Set of node IDs to focus on
            level: Level of focus isolation
        """
        self._filter_state = FilterState(
            criteria=self._filter_state.criteria,
            focus_level=level,
            focused_nodes=frozenset(node_ids),
            visible_types=self._filter_state.visible_types,
            file_filter=self._filter_state.file_filter,
            max_depth=self._filter_state.max_depth,
            custom_predicate=self._filter_state.custom_predicate,
        )

        self._update_visibility()
        self.focus_changed.emit(set(node_ids))

    def focus_on_node(self, node_id: str, level: FocusLevel = FocusLevel.NEIGHBORS) -> None:
        """Focus on a single node."""
        self.focus_on({node_id}, level)

    def clear_focus(self) -> None:
        """Clear focus and show all nodes."""
        self._filter_state = FilterState(
            criteria=self._filter_state.criteria,
            focus_level=FocusLevel.NONE,
            focused_nodes=frozenset(),
            visible_types=self._filter_state.visible_types,
            file_filter=self._filter_state.file_filter,
            max_depth=self._filter_state.max_depth,
            custom_predicate=self._filter_state.custom_predicate,
        )

        self._update_visibility()
        self.focus_changed.emit(set())

    # --- Path highlighting ---

    def highlight_path(self, from_node: str, to_node: str) -> Set[str]:
        """Find and highlight path between two nodes.

        Returns:
            Set of node IDs in the path (empty if no path found)
        """
        path = self._find_path(from_node, to_node)
        if path:
            self.focus_on(path, FocusLevel.HIGHLIGHT)
        return path

    def _find_path(self, start: str, end: str) -> Set[str]:
        """Find shortest path between nodes using BFS."""
        if start == end:
            return {start}

        visited: Set[str] = set()
        queue: List[tuple[str, List[str]]] = [(start, [start])]

        while queue:
            current, path = queue.pop(0)
            if current == end:
                return set(path)

            if current in visited:
                continue
            visited.add(current)

            # Check both directions
            neighbors = self._adjacency.get(current, set()) | self._reverse_adjacency.get(current, set())
            for neighbor in neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return set()

    # --- Visibility calculation ---

    def get_visible_nodes(self) -> Set[str]:
        """Get set of currently visible node IDs."""
        return {nid for nid, vis in self._visibility.items() if vis.visible}

    def get_highlighted_nodes(self) -> Set[str]:
        """Get set of currently highlighted node IDs."""
        return {nid for nid, vis in self._visibility.items() if vis.highlighted}

    def get_visibility(self, node_id: str) -> Optional[NodeVisibility]:
        """Get visibility state for a specific node."""
        return self._visibility.get(node_id)

    def get_all_visibility(self) -> Dict[str, NodeVisibility]:
        """Get visibility state for all nodes."""
        return dict(self._visibility)

    def _update_visibility(self) -> None:
        """Recalculate visibility for all nodes."""
        if not self._graph:
            return

        self._visibility.clear()

        # Gather nodes that pass type/file filters
        visible_by_filter = self._apply_type_and_file_filters()

        # Apply focus mode
        focus_visible, focus_highlight = self._apply_focus_mode(visible_by_filter)

        # Build final visibility
        for node in self._graph.get("nodes", []):
            node_id = node.get("id", "")
            if not node_id:
                continue

            is_visible = node_id in visible_by_filter and node_id in focus_visible
            is_highlighted = node_id in focus_highlight
            is_dimmed = (
                self._filter_state.focus_level in (FocusLevel.HIGHLIGHT, FocusLevel.NEIGHBORS, FocusLevel.EXTENDED)
                and node_id not in focus_highlight
                and is_visible
            )

            opacity = 1.0
            if is_dimmed:
                opacity = 0.3
            elif not is_visible:
                opacity = 0.0

            self._visibility[node_id] = NodeVisibility(
                node_id=node_id,
                visible=is_visible,
                highlighted=is_highlighted,
                dimmed=is_dimmed,
                opacity=opacity,
            )

        self.visibility_changed.emit(self._visibility)

    def _apply_type_and_file_filters(self) -> Set[str]:
        """Apply type and file filters to get visible nodes."""
        if not self._graph:
            return set()

        visible: Set[str] = set()

        for node in self._graph.get("nodes", []):
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            node_file = node.get("file", "")

            # Type filter
            if node_type not in self._filter_state.visible_types:
                continue

            # File filter
            if self._filter_state.file_filter:
                if self._filter_state.file_filter not in (node_file or ""):
                    continue

            # Custom predicate
            if self._filter_state.custom_predicate:
                if not self._filter_state.custom_predicate(node):
                    continue

            visible.add(node_id)

        return visible

    def _apply_focus_mode(self, filtered_nodes: Set[str]) -> tuple[Set[str], Set[str]]:
        """Apply focus mode to determine visible and highlighted nodes.

        Returns:
            Tuple of (visible_nodes, highlighted_nodes)
        """
        level = self._filter_state.focus_level
        focused = set(self._filter_state.focused_nodes)

        if level == FocusLevel.NONE or not focused:
            return filtered_nodes, set()

        # Highlighted nodes are always the focused ones
        highlighted = focused & filtered_nodes

        if level == FocusLevel.HIGHLIGHT:
            # All filtered nodes visible, focused highlighted
            return filtered_nodes, highlighted

        if level == FocusLevel.NEIGHBORS:
            # Focused + direct neighbors
            visible = set(focused)
            for nid in focused:
                visible |= self._adjacency.get(nid, set())
                visible |= self._reverse_adjacency.get(nid, set())
            return visible & filtered_nodes, highlighted

        if level == FocusLevel.EXTENDED:
            # Focused + 2-hop neighbors
            visible = set(focused)
            for nid in focused:
                neighbors = self._adjacency.get(nid, set()) | self._reverse_adjacency.get(nid, set())
                visible |= neighbors
                for neighbor in neighbors:
                    visible |= self._adjacency.get(neighbor, set())
                    visible |= self._reverse_adjacency.get(neighbor, set())
            return visible & filtered_nodes, highlighted

        if level == FocusLevel.ISOLATE:
            # Only focused nodes
            return focused & filtered_nodes, highlighted

        return filtered_nodes, highlighted

    # --- Filtering helpers ---

    def filter_to_file(self, file_path: str) -> None:
        """Filter to show only nodes from a specific file."""
        self.set_filter(
            FilterCriteria.BY_FILE,
            file_filter=file_path,
        )

    def filter_to_depth(self, max_depth: int) -> None:
        """Filter to show only nodes up to a certain depth."""
        # This requires depth information in the graph
        # For now, we filter by type as a proxy
        if max_depth == 0:
            self.set_visible_types({"module"})
        elif max_depth == 1:
            self.set_visible_types({"module", "file"})
        elif max_depth == 2:
            self.set_visible_types({"module", "file", "class"})
        else:
            self.set_visible_types({"module", "file", "class", "function", "variable"})

    def reset_filters(self) -> None:
        """Reset all filters to show everything."""
        self._filter_state = FilterState()
        self._update_visibility()
        self.filter_changed.emit(self._filter_state)
        self.focus_changed.emit(set())


def filter_graph_by_visibility(
    graph: dict,
    visibility: Dict[str, NodeVisibility],
) -> dict:
    """Create a filtered copy of the graph based on visibility.

    Args:
        graph: Original graph with nodes and edges
        visibility: Visibility state for each node

    Returns:
        New graph dict with only visible nodes and edges
    """
    visible_ids = {nid for nid, vis in visibility.items() if vis.visible}

    filtered_nodes = [
        node for node in graph.get("nodes", [])
        if node.get("id") in visible_ids
    ]

    filtered_edges = [
        edge for edge in graph.get("edges", [])
        if edge.get("source") in visible_ids and edge.get("target") in visible_ids
    ]

    return {"nodes": filtered_nodes, "edges": filtered_edges}
