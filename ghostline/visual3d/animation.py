"""Animation system for smooth 3D visualization transitions.

This module provides animation capabilities for:
- Node position transitions
- Camera movements
- Zoom animations
- Fade effects
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer, Signal
from PySide6.QtGui import QVector3D


class EasingType(Enum):
    """Supported easing curves for animations."""

    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_OUT_BOUNCE = "ease_out_bounce"
    EASE_OUT_ELASTIC = "ease_out_elastic"


def get_easing_curve(easing_type: EasingType) -> QEasingCurve:
    """Convert EasingType to Qt easing curve."""
    mapping = {
        EasingType.LINEAR: QEasingCurve.Type.Linear,
        EasingType.EASE_IN: QEasingCurve.Type.InQuad,
        EasingType.EASE_OUT: QEasingCurve.Type.OutQuad,
        EasingType.EASE_IN_OUT: QEasingCurve.Type.InOutQuad,
        EasingType.EASE_OUT_BOUNCE: QEasingCurve.Type.OutBounce,
        EasingType.EASE_OUT_ELASTIC: QEasingCurve.Type.OutElastic,
    }
    return QEasingCurve(mapping.get(easing_type, QEasingCurve.Type.OutQuad))


@dataclass
class AnimationTarget:
    """A single animation target with start/end values."""

    node_id: str
    start_position: QVector3D
    end_position: QVector3D
    current_position: QVector3D = field(default_factory=lambda: QVector3D(0, 0, 0))

    def update(self, progress: float) -> QVector3D:
        """Update position based on animation progress (0.0 to 1.0)."""
        self.current_position = self.start_position + (
            self.end_position - self.start_position
        ) * progress
        return self.current_position


@dataclass
class CameraAnimation:
    """Camera animation parameters."""

    start_position: QVector3D
    end_position: QVector3D
    start_center: QVector3D
    end_center: QVector3D
    current_position: QVector3D = field(default_factory=lambda: QVector3D(0, 0, 0))
    current_center: QVector3D = field(default_factory=lambda: QVector3D(0, 0, 0))

    def update(self, progress: float) -> tuple[QVector3D, QVector3D]:
        """Update camera position and view center based on progress."""
        self.current_position = self.start_position + (
            self.end_position - self.start_position
        ) * progress
        self.current_center = self.start_center + (
            self.end_center - self.start_center
        ) * progress
        return self.current_position, self.current_center


class AnimationController(QObject):
    """Controller for managing and running animations.

    Signals:
        animation_started: Emitted when animation begins
        animation_finished: Emitted when animation completes
        frame_updated: Emitted each frame with current progress (0.0-1.0)
        positions_updated: Emitted with updated node positions dict
    """

    animation_started = Signal()
    animation_finished = Signal()
    frame_updated = Signal(float)  # progress
    positions_updated = Signal(dict)  # node_id -> QVector3D

    def __init__(
        self,
        duration_ms: int = 500,
        fps: int = 60,
        easing: EasingType = EasingType.EASE_OUT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._duration = duration_ms
        self._fps = fps
        self._easing = easing
        self._easing_curve = get_easing_curve(easing)

        self._targets: Dict[str, AnimationTarget] = {}
        self._camera_anim: Optional[CameraAnimation] = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._frame_interval = 1000 // fps

        self._elapsed = 0
        self._running = False

        # Callbacks
        self._on_complete: Optional[Callable[[], None]] = None
        self._position_callback: Optional[Callable[[Dict[str, QVector3D]], None]] = None
        self._camera_callback: Optional[Callable[[QVector3D, QVector3D], None]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, value: int) -> None:
        self._duration = max(1, value)

    def set_easing(self, easing: EasingType) -> None:
        """Set the easing curve for animations."""
        self._easing = easing
        self._easing_curve = get_easing_curve(easing)

    def set_position_callback(
        self, callback: Callable[[Dict[str, QVector3D]], None]
    ) -> None:
        """Set callback for position updates during animation."""
        self._position_callback = callback

    def set_camera_callback(
        self, callback: Callable[[QVector3D, QVector3D], None]
    ) -> None:
        """Set callback for camera updates during animation."""
        self._camera_callback = callback

    def set_completion_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for animation completion."""
        self._on_complete = callback

    # --- Animation setup ---

    def clear_targets(self) -> None:
        """Clear all animation targets."""
        self._targets.clear()
        self._camera_anim = None

    def add_target(
        self,
        node_id: str,
        start_position: QVector3D,
        end_position: QVector3D,
    ) -> None:
        """Add a node position animation target."""
        self._targets[node_id] = AnimationTarget(
            node_id=node_id,
            start_position=start_position,
            end_position=end_position,
            current_position=QVector3D(start_position),
        )

    def set_camera_animation(
        self,
        start_position: QVector3D,
        end_position: QVector3D,
        start_center: QVector3D,
        end_center: QVector3D,
    ) -> None:
        """Set camera animation parameters."""
        self._camera_anim = CameraAnimation(
            start_position=start_position,
            end_position=end_position,
            start_center=start_center,
            end_center=end_center,
            current_position=QVector3D(start_position),
            current_center=QVector3D(start_center),
        )

    # --- Animation control ---

    def start(self) -> None:
        """Start the animation."""
        if self._running:
            self.stop()

        self._elapsed = 0
        self._running = True
        self._timer.start(self._frame_interval)
        self.animation_started.emit()

    def stop(self) -> None:
        """Stop the animation immediately."""
        self._timer.stop()
        self._running = False

    def finish(self) -> None:
        """Skip to the end of the animation."""
        self._timer.stop()
        self._update_frame(1.0)
        self._running = False
        self.animation_finished.emit()
        if self._on_complete:
            self._on_complete()

    def _on_tick(self) -> None:
        """Handle animation timer tick."""
        self._elapsed += self._frame_interval

        if self._elapsed >= self._duration:
            self.finish()
            return

        linear_progress = self._elapsed / self._duration
        eased_progress = self._easing_curve.valueForProgress(linear_progress)
        self._update_frame(eased_progress)

    def _update_frame(self, progress: float) -> None:
        """Update all targets for current frame."""
        # Update node positions
        if self._targets:
            positions = {}
            for node_id, target in self._targets.items():
                positions[node_id] = target.update(progress)

            self.positions_updated.emit(positions)
            if self._position_callback:
                self._position_callback(positions)

        # Update camera
        if self._camera_anim and self._camera_callback:
            pos, center = self._camera_anim.update(progress)
            self._camera_callback(pos, center)

        self.frame_updated.emit(progress)


class TransitionManager(QObject):
    """High-level manager for common animation transitions.

    Provides convenient methods for:
    - Layout transitions (animate between layouts)
    - Focus transitions (zoom to a node)
    - Filter transitions (fade nodes in/out)
    """

    transition_started = Signal()
    transition_finished = Signal()

    def __init__(
        self,
        duration_ms: int = 400,
        easing: EasingType = EasingType.EASE_OUT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = AnimationController(
            duration_ms=duration_ms,
            easing=easing,
            parent=self,
        )
        self._controller.animation_started.connect(self.transition_started.emit)
        self._controller.animation_finished.connect(self.transition_finished.emit)

        self._current_positions: Dict[str, QVector3D] = {}

    @property
    def controller(self) -> AnimationController:
        return self._controller

    @property
    def is_animating(self) -> bool:
        return self._controller.is_running

    def set_current_positions(self, positions: Dict[str, QVector3D]) -> None:
        """Set the current node positions (start of next transition)."""
        self._current_positions = dict(positions)

    def animate_to_positions(
        self,
        target_positions: Dict[str, QVector3D],
        on_update: Optional[Callable[[Dict[str, QVector3D]], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Animate from current positions to target positions.

        Args:
            target_positions: Target positions for each node
            on_update: Called each frame with updated positions
            on_complete: Called when animation finishes
        """
        self._controller.clear_targets()

        # Add targets for nodes that exist in both current and target
        for node_id, target_pos in target_positions.items():
            start_pos = self._current_positions.get(node_id, target_pos)
            self._controller.add_target(node_id, start_pos, target_pos)

        if on_update:
            self._controller.set_position_callback(on_update)
        if on_complete:
            self._controller.set_completion_callback(on_complete)

        self._controller.start()

        # Update current positions to targets when done
        self._current_positions = dict(target_positions)

    def animate_camera_to(
        self,
        target_position: QVector3D,
        target_center: QVector3D,
        current_position: QVector3D,
        current_center: QVector3D,
        on_update: Callable[[QVector3D, QVector3D], None],
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Animate camera to a new position and view center.

        Args:
            target_position: Target camera position
            target_center: Target view center
            current_position: Current camera position
            current_center: Current view center
            on_update: Called each frame with camera position and center
            on_complete: Called when animation finishes
        """
        self._controller.clear_targets()
        self._controller.set_camera_animation(
            current_position, target_position,
            current_center, target_center,
        )
        self._controller.set_camera_callback(on_update)
        if on_complete:
            self._controller.set_completion_callback(on_complete)

        self._controller.start()

    def skip_to_end(self) -> None:
        """Skip current animation to end state."""
        if self._controller.is_running:
            self._controller.finish()


class FadeTransition:
    """Helper class for fade in/out effects on nodes.

    This provides opacity values that can be applied to node materials.
    """

    def __init__(self, duration_ms: int = 300) -> None:
        self._duration = duration_ms
        self._opacity_map: Dict[str, float] = {}

    def fade_in(
        self,
        node_ids: List[str],
        on_update: Callable[[Dict[str, float]], None],
        on_complete: Optional[Callable[[], None]] = None,
    ) -> AnimationController:
        """Create a fade-in animation for nodes."""
        controller = AnimationController(duration_ms=self._duration)

        def update_opacity(progress: float) -> None:
            opacities = {nid: progress for nid in node_ids}
            on_update(opacities)

        controller.frame_updated.connect(update_opacity)
        if on_complete:
            controller.set_completion_callback(on_complete)

        controller.start()
        return controller

    def fade_out(
        self,
        node_ids: List[str],
        on_update: Callable[[Dict[str, float]], None],
        on_complete: Optional[Callable[[], None]] = None,
    ) -> AnimationController:
        """Create a fade-out animation for nodes."""
        controller = AnimationController(duration_ms=self._duration)

        def update_opacity(progress: float) -> None:
            opacities = {nid: 1.0 - progress for nid in node_ids}
            on_update(opacities)

        controller.frame_updated.connect(update_opacity)
        if on_complete:
            controller.set_completion_callback(on_complete)

        controller.start()
        return controller
