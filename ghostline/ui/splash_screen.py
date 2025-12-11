from __future__ import annotations

import random

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class ServiceStatusBar(QWidget):
    """Segmented neon-like service status indicator."""

    def __init__(self, name: str, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.color = color
        self.progress = 0
        self.setMinimumHeight(26)
        self.setMaximumHeight(32)

    def set_progress(self, value: int) -> None:
        self.progress = max(0, min(100, value))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(6, 4, -6, -4)

        # Label
        label_text = f"[ {self.name.upper()} ]"
        font = painter.font()
        font.setPointSize(10)
        font.setFamily("JetBrains Mono")
        painter.setFont(font)
        painter.setPen(QColor(160, 174, 192))
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, label_text)

        # Bar area
        bar_x = painter.fontMetrics().horizontalAdvance(label_text) + 12
        bar_rect = rect.adjusted(bar_x, 2, 0, -2)
        segment_count = 16
        segment_spacing = 3
        segment_width = (bar_rect.width() - (segment_count - 1) * segment_spacing) / segment_count
        active_segments = int(segment_count * (self.progress / 100))

        base_color = QColor(40, 46, 64)
        painter.setPen(Qt.NoPen)
        painter.setBrush(base_color)
        painter.drawRoundedRect(bar_rect, 6, 6)

        for i in range(segment_count):
            x = bar_rect.x() + i * (segment_width + segment_spacing) + 3
            seg_rect = QRectF(x, bar_rect.y() + 4, segment_width - 6, bar_rect.height() - 8)
            if i < active_segments:
                painter.setBrush(self.color)
            else:
                painter.setBrush(QColor(22, 26, 36))
            painter.drawRoundedRect(seg_rect, 3, 3)

        # Highlight overlay when near completion
        if self.progress >= 90:
            overlay = QColor(self.color)
            overlay.setAlpha(60)
            painter.setBrush(overlay)
            painter.drawRoundedRect(bar_rect.adjusted(0, 0, 0, -bar_rect.height() * 0.25), 6, 6)

        painter.end()


class LogoWidget(QWidget):
    """Custom widget to paint the Ghostline logo with glitch effects."""

    def __init__(self, splash: "GhostlineSplash", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.splash = splash
        self.setMinimumHeight(170)
        self.setMaximumHeight(220)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        base_font = QFont("Orbitron", 42, QFont.Bold)
        if "Orbitron" not in QFontDatabase().families():
            base_font = QFont("Montserrat", 42, QFont.Bold)
        painter.setFont(base_font)

        text = self.splash.logo_text[: self.splash.logo_visible_chars]
        if not text:
            return

        text_width = painter.fontMetrics().horizontalAdvance(text)
        text_height = painter.fontMetrics().height()
        x = (rect.width() - text_width) / 2
        y = (rect.height() + text_height) / 2 - 10

        jitter = self.splash.logo_glitch_offset if self.splash.glitch_active else QPointF(0, 0)
        pos = QPointF(x, y) + jitter

        path = QPainterPath()
        path.addText(pos, base_font, text)

        accent = QColor(93, 194, 255)
        outline_pen = QPen(accent, 2)
        outline_pen.setJoinStyle(Qt.MiterJoin)

        # RGB split shadows during glitch
        if self.splash.glitch_active and random.random() > 0.6:
            for dx, color in [(-2, QColor(255, 90, 132)), (2, QColor(0, 255, 166))]:
                painter.save()
                painter.translate(dx, 0)
                painter.setPen(QPen(color, 2))
                painter.drawPath(path)
                painter.restore()

        painter.setPen(outline_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Fill when phase allows
        if self.splash.logo_fill_amount > 0:
            fill_color = QColor(240, 247, 255)
            fill_color.setAlphaF(min(1.0, self.splash.logo_fill_amount))
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill_color)
            painter.drawPath(path)

        painter.end()


class GhostlineSplash(QWidget):
    """Animated sci-fi splash screen for Ghostline Studio."""

    splashFinished = Signal()

    def __init__(self, wait_for_dependencies: bool = True) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(900, 500)

        self.logo_text = "GHOSTLINE STUDIO"
        self.logo_visible_chars = 0
        self.logo_fill_amount = 0.0
        self.logo_glitch_offset = QPointF(0, 0)
        self.glitch_active = True
        self.services_complete = False
        self.minimum_display_ms = 2600
        self._fade_started = False
        self._wait_for_dependencies = wait_for_dependencies
        self._dependency_setup_complete = False

        self._setup_layout()
        self._setup_effects()
        self._setup_timers()

    def _setup_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.logo_widget = LogoWidget(self)
        layout.addWidget(self.logo_widget)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFrameStyle(QFrame.NoFrame)
        self.terminal.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.terminal.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        terminal_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        terminal_font.setPointSize(10)
        self.terminal.setFont(terminal_font)
        self.terminal.setStyleSheet(
            "QPlainTextEdit {"
            "background: rgba(5, 6, 10, 200);"
            "color: #a0ffa0;"
            "selection-background-color: rgba(80, 150, 255, 80);"
            "border-radius: 8px;"
            "padding: 8px;"
            "}"
        )
        self.terminal.setMaximumBlockCount(200)
        layout.addWidget(self.terminal, 1)

        self.status_container = QWidget()
        status_layout = QVBoxLayout(self.status_container)
        status_layout.setContentsMargins(6, 6, 6, 6)
        status_layout.setSpacing(6)

        self.core_status = ServiceStatusBar("CORE", QColor(79, 140, 255))
        self.net_status = ServiceStatusBar("NET", QColor(58, 211, 122))
        self.ai_status = ServiceStatusBar("AI", QColor(255, 79, 163))

        status_layout.addWidget(self.core_status)
        status_layout.addWidget(self.net_status)
        status_layout.addWidget(self.ai_status)

        layout.addWidget(self.status_container)

    def _setup_effects(self) -> None:
        self.logo_opacity_effect = QGraphicsOpacityEffect(self.logo_widget)
        self.logo_widget.setGraphicsEffect(self.logo_opacity_effect)
        self.logo_opacity_effect.setOpacity(0.0)

        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(520)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_animation.finished.connect(self._on_fade_finished)

    def _setup_timers(self) -> None:
        self.elapsed = 0
        self.timeline_timer = QTimer(self)
        self.timeline_timer.setInterval(60)
        self.timeline_timer.timeout.connect(self._update_timeline)
        self.timeline_timer.start()

        self.glitch_timer = QTimer(self)
        self.glitch_timer.setInterval(70)
        self.glitch_timer.timeout.connect(self._update_glitch)
        self.glitch_timer.start()

        self.terminal_timer = QTimer(self)
        self.terminal_timer.setInterval(32)
        self.terminal_timer.timeout.connect(self._append_terminal_line)
        self.terminal_timer.start()

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(80)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start()

        self.radar_timer = QTimer(self)
        self.radar_timer.setInterval(50)
        self.radar_timer.timeout.connect(self._update_radar)
        self.radar_timer.start()

        self.radar_angle = 0.0
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        screen = self.screen()
        if screen:
            geometry = screen.geometry()
            x = geometry.center().x() - self.width() // 2
            y = geometry.center().y() - self.height() // 2
            self.move(x, y)

    # Timers and animations
    def _update_timeline(self) -> None:
        self.elapsed += self.timeline_timer.interval()
        elapsed = self.elapsed

        if elapsed < 800:
            step = max(1, int(elapsed / 40))
            self.logo_visible_chars = min(len(self.logo_text), step)
            self.logo_opacity_effect.setOpacity(random.uniform(0.4, 0.9))
            self.glitch_active = True
        elif elapsed < 1600:
            self.logo_visible_chars = len(self.logo_text)
            self.logo_opacity_effect.setOpacity(random.uniform(0.3, 1.0))
            self.glitch_active = True
        elif elapsed < 2200:
            self.glitch_active = False
            self.logo_fill_amount = min(1.0, (elapsed - 1600) / 600)
            self.logo_opacity_effect.setOpacity(1.0)
        else:
            self.glitch_active = False
            self.logo_fill_amount = 1.0
            self.logo_opacity_effect.setOpacity(1.0)

        self.logo_widget.update()
        self.update()

        # Only close splash when both animation is done AND dependencies are ready
        can_close = elapsed >= self.minimum_display_ms and self.services_complete
        if self._wait_for_dependencies:
            can_close = can_close and self._dependency_setup_complete

        if can_close:
            self._start_fade_out()

    def _update_glitch(self) -> None:
        if self.glitch_active:
            self.logo_glitch_offset = QPointF(random.uniform(-2.5, 2.5), random.uniform(-2.5, 2.5))
            self.logo_opacity_effect.setOpacity(random.uniform(0.4, 1.0))
        else:
            self.logo_glitch_offset = QPointF(0, 0)

        self.logo_widget.update()

    def _append_terminal_line(self) -> None:
        pool = [
            "0x3F12A7    INIT    checksum=OK",
            "[CORE]   loading ghostline.kernel :: OK",
            "[AI]     bootstrapping multi-agent mesh :: STABLE",
            "[NET]    uplink: 192.168.0.1/online   latency=12ms",
            "[SYS]    integrity scan: PASSED",
            "[DNS]    resolving ghostline.studio -> 10.0.0.42",
            "[SAT]    uplink channel locked :: SNR=38dB",
            "[IO]     mounting virtual FS :: READY",
            "[GPU]    initializing neural cores :: GREEN",
            "[SEC]    quantum handshake verified",
        ]
        line = random.choice(pool)
        self.terminal.appendPlainText(line)
        scroll_bar = self.terminal.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _update_status(self) -> None:
        if self.services_complete:
            return

        increments = {
            self.core_status: random.randint(4, 9),
            self.net_status: random.randint(2, 6),
            self.ai_status: random.randint(2, 6),
        }
        for widget, inc in increments.items():
            widget.set_progress(min(100, widget.progress + inc))

        if all(w.progress >= 100 for w in increments.keys()):
            self.services_complete = True

    def _update_radar(self) -> None:
        self.radar_angle = (self.radar_angle + 3.6) % 360
        if not self.glitch_active:
            self.radar_timer.setInterval(70)
        self.update()

    def _start_fade_out(self) -> None:
        if self._fade_started:
            return
        self._fade_started = True
        for timer in [self.timeline_timer, self.glitch_timer, self.terminal_timer, self.status_timer, self.radar_timer]:
            timer.stop()
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

    def _on_fade_finished(self) -> None:
        self.splashFinished.emit()
        self.close()

    # Painting overlays
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background gradient
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(5, 6, 10))
        gradient.setColorAt(1.0, QColor(16, 18, 26))
        painter.fillRect(self.rect(), gradient)

        self._draw_grid(painter)
        self._draw_radar(painter)
        self._draw_scanlines(painter)
        self._draw_vignette(painter)
        if self.glitch_active:
            self._draw_noise(painter)

        painter.end()

    def _draw_grid(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QPen(QColor(32, 35, 50, 60), 1))
        spacing = 40
        for x in range(0, self.width(), spacing):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), spacing):
            painter.drawLine(0, y, self.width(), y)
        painter.restore()

    def _draw_radar(self, painter: QPainter) -> None:
        painter.save()
        center = QPointF(self.width() * 0.78, self.height() * 0.54)
        radius = 160
        base_color = QColor(79, 140, 255, 40)
        painter.setPen(QPen(base_color, 1))
        for r in range(60, radius, 30):
            painter.drawEllipse(center, r, r)

        painter.setPen(Qt.NoPen)
        sweep_color = QColor(79, 140, 255, 90)
        path = QPainterPath()
        path.moveTo(center)
        path.arcTo(center.x() - radius, center.y() - radius, radius * 2, radius * 2, -self.radar_angle, -25)
        path.lineTo(center)
        painter.setBrush(sweep_color)
        painter.drawPath(path)
        painter.restore()

    def _draw_scanlines(self, painter: QPainter) -> None:
        painter.save()
        scan_color = QColor(255, 255, 255, 10)
        painter.setPen(Qt.NoPen)
        for y in range(0, self.height(), 4):
            painter.fillRect(0, y, self.width(), 1, scan_color)
        painter.restore()

    def _draw_vignette(self, painter: QPainter) -> None:
        painter.save()
        vignette = QRadialGradient(self.rect().center(), self.width() * 0.8)
        vignette.setColorAt(0.7, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        painter.fillRect(self.rect(), vignette)
        painter.restore()

    def _draw_noise(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        for _ in range(14):
            w, h = random.randint(8, 28), random.randint(1, 6)
            x = random.randint(0, self.width())
            y = random.randint(0, self.height())
            color = QColor(random.choice([79, 140, 255, 255, 79, 163]), random.randint(120, 255), random.randint(120, 255), 120)
            painter.fillRect(x, y, w, h, color)
        painter.restore()

    # Public API for dependency setup
    def update_status(self, message: str) -> None:
        """Update the splash screen with a progress message.

        Args:
            message: Status message to display in the terminal
        """
        self.terminal.appendPlainText(f"[SETUP] {message}")
        scroll_bar = self.terminal.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def mark_dependency_setup_complete(self, success: bool) -> None:
        """Mark dependency setup as complete.

        Args:
            success: Whether dependency setup completed successfully
        """
        self._dependency_setup_complete = True
        if success:
            self.terminal.appendPlainText("[SETUP] Dependencies ready")
        else:
            self.terminal.appendPlainText("[SETUP] Dependency setup encountered errors")
