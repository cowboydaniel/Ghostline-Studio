"""3D visualization components for Ghostline Studio.

This package provides architecture visualization using Qt3D with
an OpenGL fallback for environments without Qt3D support.

Modules:
- architecture_scene: Main 3D scene widget with Qt3D rendering
- architecture_dock: Dockable UI container with controls
- layout_algorithms: Graph layout algorithms (force-directed, hierarchical, etc.)
- animation: Smooth animation transitions
- focus_mode: Filtering and focus mode management
- fallback_renderer: 2D QPainter-based fallback renderer
- export: Export to PNG, SVG, JSON formats
"""

from .architecture_dock import ArchitectureDock
from .architecture_scene import ArchitectureScene
from .layout_algorithms import (
    LayoutConfig,
    LayoutEngine,
    LayoutNode,
    LayoutEdge,
    LayoutType,
    compute_graph_layout,
)
from .animation import (
    AnimationController,
    EasingType,
    TransitionManager,
    FadeTransition,
)
from .focus_mode import (
    FilterCriteria,
    FilterState,
    FocusLevel,
    FocusModeManager,
    NodeVisibility,
    filter_graph_by_visibility,
)
from .export import (
    ExportConfig,
    ExportFormat,
    ExportManager,
    quick_export_png,
)
from .fallback_renderer import FallbackRenderer

__all__ = [
    # Main components
    "ArchitectureDock",
    "ArchitectureScene",
    # Layout
    "LayoutConfig",
    "LayoutEngine",
    "LayoutNode",
    "LayoutEdge",
    "LayoutType",
    "compute_graph_layout",
    # Animation
    "AnimationController",
    "EasingType",
    "TransitionManager",
    "FadeTransition",
    # Focus mode
    "FilterCriteria",
    "FilterState",
    "FocusLevel",
    "FocusModeManager",
    "NodeVisibility",
    "filter_graph_by_visibility",
    # Export
    "ExportConfig",
    "ExportFormat",
    "ExportManager",
    "quick_export_png",
    # Fallback
    "FallbackRenderer",
]
