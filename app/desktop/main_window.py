from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from typing import Any
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QTextBrowser,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
)

from app.core.config import settings
from app.engine.llm import LLMDecisionMaker
from app.engine.rag import generate_diagnostic_report
from app.engine.sandbox import AgentSpawner, SandboxEnvironment, SimulationSnapshot

SCENE_WIDTH = 720.0
SCENE_HEIGHT = 460.0

LINEAR_QSS = """
QMainWindow {
    background: #0a0a0a;
    color: #f7f8f8;
}
QWidget {
    background: transparent;
    color: #d0d6e0;
    font-family: "Inter Variable", "SF Pro Display", "Segoe UI", sans-serif;
    font-size: 14px;
}
QFrame#Card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
}
QFrame#CanvasCard {
    background: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
}
QLabel#Title {
    color: #f7f8f8;
    font-size: 20px;
    font-weight: 590;
}
QLabel#Meta {
    color: #8a8f98;
    font-size: 13px;
}
QLabel#Badge {
    color: #d0d6e0;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 510;
}
QPushButton {
    background: #5e6ad2;
    color: #f7f8f8;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 510;
}
QPushButton:hover {
    background: #7170ff;
}
QPushButton#PrimaryButton {
    background: #5e6ad2;
    color: #f7f8f8;
    border: 1px solid rgba(255, 255, 255, 0.10);
}
QPushButton#PrimaryButton:hover {
    background: #7170ff;
}
QLineEdit {
    background: rgba(255, 255, 255, 0.02);
    color: #f7f8f8;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: #7170ff;
}
QPlainTextEdit {
    background: #17181a;
    color: #d0d6e0;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 12px 14px;
    font-family: "Berkeley Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #5e6ad2;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -6px 0;
    background: #f7f8f8;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 7px;
}
QGraphicsView {
    background: #0a0a0a;
    border: none;
}
QSplitter::handle {
    background: rgba(255, 255, 255, 0.10);
    width: 1px;
}
"""


class SandboxCanvas(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.scene_ref = QGraphicsScene(self)
        self.setScene(self.scene_ref)
        self.setSceneRect(QRectF(0, 0, SCENE_WIDTH, SCENE_HEIGHT))
        self.scene_ref.setBackgroundBrush(QColor("#08090a"))
        self.overlay_font = QFont("Cascadia Code", 9)
        self.title_font = QFont("Inter Variable", 10)
        self.show_mitigation = False

    def render_snapshot(self, snapshot: SimulationSnapshot, env: SandboxEnvironment) -> None:
        self.scene_ref.clear()
        self._draw_backdrop()
        self._draw_site_context(env)
        self._draw_heatmap(snapshot, env)
        self._draw_guides(env)
        self._draw_agents(snapshot, env)
        self._draw_hud(snapshot)

    def set_mitigation_visible(self, visible: bool) -> None:
        self.show_mitigation = visible

    def _draw_backdrop(self) -> None:
        self.scene_ref.addRect(0.0, 0.0, SCENE_WIDTH, SCENE_HEIGHT, QPen(Qt.NoPen), QBrush(QColor("#0a0a0a")))

        grid_pen = QPen(QColor(255, 255, 255, 12))
        grid_pen.setWidthF(1.0)
        for x in range(48, int(SCENE_WIDTH), 48):
            self.scene_ref.addLine(float(x), 0.0, float(x), SCENE_HEIGHT, grid_pen)
        for y in range(46, int(SCENE_HEIGHT), 46):
            self.scene_ref.addLine(0.0, float(y), SCENE_WIDTH, float(y), grid_pen)

    def _draw_site_context(self, env: SandboxEnvironment) -> None:
        layout = env.get_layout_profile()
        corridor = self._normalized_polygon(layout["corridor_polygon"])
        context_polygons = [self._normalized_polygon(points) for points in layout["context_polygons"]]
        hazard_zone = self._normalized_polygon(layout["hazard_zone"])

        for polygon, tone in zip(context_polygons, (QColor(20, 22, 28, 230), QColor(18, 20, 26, 236)), strict=False):
            self.scene_ref.addPolygon(polygon, QPen(Qt.NoPen), QBrush(tone))

        self.scene_ref.addPolygon(corridor, QPen(QColor(255, 255, 255, 60), 1.2), QBrush(QColor("#17181a")))

        wall_pen = QPen(QColor(255, 255, 255, 72))
        wall_pen.setWidthF(1.4)
        for start, end in self._polygon_edges(corridor):
            self.scene_ref.addLine(start.x(), start.y(), end.x(), end.y(), wall_pen)

        for t in (0.2, 0.4, 0.6, 0.8):
            start = self._lerp_point(corridor[0], corridor[1], t)
            end = self._lerp_point(corridor[3], corridor[2], t)
            lane_pen = QPen(QColor(255, 255, 255, 20))
            lane_pen.setStyle(Qt.DashLine)
            lane_pen.setWidthF(1.0)
            self.scene_ref.addLine(start.x(), start.y(), end.x(), end.y(), lane_pen)

        self.scene_ref.addPolygon(
            hazard_zone,
            QPen(QColor(180, 106, 106, 90), 1.0),
            QBrush(QColor(122, 70, 70, 26)),
        )

        if self.show_mitigation:
            for barrier in layout.get("mitigation_barriers", []):
                start = self._project_normalized(barrier[0][0], barrier[0][1])
                end = self._project_normalized(barrier[1][0], barrier[1][1])
                barrier_pen = QPen(QColor("#7170ff"))
                barrier_pen.setWidthF(2.0)
                self.scene_ref.addLine(start.x(), start.y(), end.x(), end.y(), barrier_pen)
            self._add_overlay_label("Mitigation overlay: virtual barriers", QPointF(422.0, 410.0), QColor("#7170ff"), self.overlay_font)

        tone_map = {
            "accent": QColor("#d0d6e0"),
            "info": QColor("#8a8f98"),
            "danger": QColor("#b46a6a"),
        }
        for label in layout.get("labels", []):
            point = self._project_normalized(label["position"][0], label["position"][1])
            font = self.title_font if label.get("tone") == "danger" else self.overlay_font
            self._add_overlay_label(label["text"], point, tone_map.get(label.get("tone", "info"), QColor("#dbeafe")), font)

    def _draw_guides(self, env: SandboxEnvironment) -> None:
        left_mid = self._project_world_point(0.15, env.height_m * 0.5, env)
        right_mid = self._project_world_point(env.width_m - 0.15, env.height_m * 0.5, env)

        north_pen = QPen(QColor("#7170ff"))
        north_pen.setWidthF(2.2)
        south_pen = QPen(QColor("#8a8f98"))
        south_pen.setWidthF(2.2)
        self.scene_ref.addLine(left_mid.x() - 30.0, left_mid.y() + 24.0, left_mid.x() + 12.0, left_mid.y() + 6.0, north_pen)
        self.scene_ref.addLine(right_mid.x() + 28.0, right_mid.y() - 18.0, right_mid.x() - 10.0, right_mid.y() - 4.0, south_pen)
        self._add_overlay_label("Northbound inflow", QPointF(left_mid.x() - 42.0, left_mid.y() + 32.0), QColor("#d0d6e0"), self.overlay_font)
        self._add_overlay_label("Southbound inflow", QPointF(right_mid.x() - 56.0, right_mid.y() - 42.0), QColor("#8a8f98"), self.overlay_font)

    def _draw_heatmap(self, snapshot: SimulationSnapshot, env: SandboxEnvironment) -> None:
        grid = snapshot.density_grid
        rows, cols = grid.shape
        for row in range(rows):
            for col in range(cols):
                if not env.walkable_mask[row, col]:
                    continue
                value = float(grid[row, col])
                if value <= 0.08:
                    continue
                x0 = col * env.resolution_m
                x1 = min(env.width_m, (col + 1) * env.resolution_m)
                y0 = row * env.resolution_m
                y1 = min(env.height_m, (row + 1) * env.resolution_m)
                cell = QPolygonF(
                    [
                        self._project_world_point(x0, y0, env),
                        self._project_world_point(x1, y0, env),
                        self._project_world_point(x1, y1, env),
                        self._project_world_point(x0, y1, env),
                    ]
                )
                self.scene_ref.addPolygon(cell, QPen(Qt.NoPen), QBrush(self._density_color(value)))

    def _draw_agents(self, snapshot: SimulationSnapshot, env: SandboxEnvironment) -> None:
        for agent in snapshot.agent_snapshots:
            point = self._project_world_point(agent.x, agent.y, env)
            radius = 7.2 if agent.mode == "slow" else 5.6
            shadow = QGraphicsEllipseItem(point.x() - radius + 2.4, point.y() - radius + 3.6, radius * 2.0, radius * 2.0)
            shadow.setBrush(QColor(0, 0, 0, 92))
            shadow.setPen(QPen(Qt.NoPen))
            self.scene_ref.addItem(shadow)

            color = QColor("#b46a6a") if agent.mode == "slow" else QColor("#b7c0cb")
            dot = QGraphicsEllipseItem(point.x() - radius, point.y() - radius, radius * 2.0, radius * 2.0)
            dot.setBrush(color)
            dot.setPen(QPen(QColor(255, 255, 255, 38), 0.8))
            self.scene_ref.addItem(dot)

            trail_target = self._project_world_point(
                max(0.0, min(env.width_m, agent.x - (agent.vx * 0.24))),
                max(0.0, min(env.height_m, agent.y - (agent.vy * 0.24))),
                env,
            )
            trail_pen = QPen(QColor(color.red(), color.green(), color.blue(), 90))
            trail_pen.setWidthF(1.3)
            self.scene_ref.addLine(trail_target.x(), trail_target.y(), point.x(), point.y(), trail_pen)

    def _draw_hud(self, snapshot: SimulationSnapshot) -> None:
        self.scene_ref.addRect(18.0, 16.0, 220.0, 70.0, QPen(QColor(255, 255, 255, 28), 1.0), QBrush(QColor(17, 18, 19, 196)))
        self._add_overlay_label("Itaewon alley digital twin", QPointF(30.0, 24.0), QColor("#f8fafc"), self.title_font)
        self._add_overlay_label(
            f"step={snapshot.step_index:04d}  peak={snapshot.peak_density:.2f}  local={snapshot.max_local_density:.2f}",
            QPointF(30.0, 48.0),
            QColor("#94a3b8"),
            self.overlay_font,
        )
        self._add_overlay_label(
            f"active={snapshot.active_agents}  slow={snapshot.slow_brain_request_count}  freeze={int(snapshot.frozen_this_step)}",
            QPointF(30.0, 65.0),
            QColor("#94a3b8"),
            self.overlay_font,
        )

    def _project_world_point(self, x: float, y: float, env: SandboxEnvironment) -> QPointF:
        nx = min(max(x / max(env.width_m, 1e-6), 0.0), 1.0)
        ny = min(max(y / max(env.height_m, 1e-6), 0.0), 1.0)
        top_left = QPointF(108.0, 126.0)
        top_right = QPointF(610.0, 92.0)
        bottom_left = QPointF(86.0, 388.0)
        bottom_right = QPointF(654.0, 346.0)
        top = self._lerp_point(top_left, top_right, nx)
        bottom = self._lerp_point(bottom_left, bottom_right, nx)
        return self._lerp_point(top, bottom, ny)

    def _project_normalized(self, nx: float, ny: float) -> QPointF:
        top_left = QPointF(108.0, 126.0)
        top_right = QPointF(610.0, 92.0)
        bottom_left = QPointF(86.0, 388.0)
        bottom_right = QPointF(654.0, 346.0)
        top = self._lerp_point(top_left, top_right, nx)
        bottom = self._lerp_point(bottom_left, bottom_right, nx)
        return self._lerp_point(top, bottom, ny)

    def _lerp_point(self, start: QPointF, end: QPointF, t: float) -> QPointF:
        clamped = min(max(t, 0.0), 1.0)
        return QPointF(
            start.x() + ((end.x() - start.x()) * clamped),
            start.y() + ((end.y() - start.y()) * clamped),
        )

    def _normalized_polygon(self, points: list[tuple[float, float]]) -> QPolygonF:
        return QPolygonF([self._project_normalized(x, y) for x, y in points])

    def _polygon_edges(self, polygon: QPolygonF) -> list[tuple[QPointF, QPointF]]:
        edges: list[tuple[QPointF, QPointF]] = []
        for index in range(len(polygon)):
            edges.append((polygon[index], polygon[(index + 1) % len(polygon)]))
        return edges

    def _add_overlay_label(self, text: str, point: QPointF, color: QColor, font: QFont) -> None:
        label = self.scene_ref.addText(text, font)
        label.setDefaultTextColor(color)
        label.setPos(point)

    def _density_color(self, density: float) -> QColor:
        if density >= 12.0:
            return QColor(196, 39, 52, 230)
        if density >= 7.0:
            return QColor(255, 110, 64, 180)
        if density >= 5.0:
            return QColor(255, 184, 77, 140)
        return QColor(16, 185, 129, 88)


class AsyncSimulationBridge(QObject):
    snapshot_ready = Signal(object)
    log_received = Signal(str)
    status_changed = Signal(str)
    report_ready = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self.left_rate = 2.5
        self.right_rate = 2.5
        self.env = self._build_environment()
        self.decision_maker = LLMDecisionMaker(
            base_url=settings.local_llm_base_url,
            api_key=settings.local_llm_api_key or "EMPTY",
            model=settings.local_llm_model,
        )
        self.all_slow_logs: list[dict[str, Any]] = []
        self.peak_density_overall = 0.0

    @Slot()
    def start(self) -> None:
        if self._running:
            return
        self.env = self._build_environment()
        self.all_slow_logs = []
        self.peak_density_overall = 0.0
        self._running = True
        self.status_changed.emit("simulation-started")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    @Slot()
    def stop(self) -> None:
        self._running = False
        self.status_changed.emit("simulation-stopped")

    @Slot()
    def generate_report(self) -> None:
        if self._running:
            self.status_changed.emit("Stop simulation before generating report.")
            return

        def _run_rag() -> None:
            self.status_changed.emit("Generating diagnostic report via RAG...")
            payload = {
                "peak_density": self.peak_density_overall,
                "deadlock_seconds": 0.0, # Approximate
                "slow_brain_trigger_count": len(self.all_slow_logs),
                "raw": self.all_slow_logs[:50], # Sample
            }
            try:
                report = generate_diagnostic_report(payload)
                self.report_ready.emit(report)
            except Exception as e:
                self.report_ready.emit(f"Failed to generate report: {e}")

        threading.Thread(target=_run_rag, daemon=True).start()

    @Slot(float, float)
    def update_arrival_rates(self, left: float, right: float) -> None:
        with self._lock:
            self.left_rate = left
            self.right_rate = right
        self.status_changed.emit(f"arrival-updated:{left:.2f}/{right:.2f}")

    def _run_loop(self) -> None:
        asyncio.run(self._simulation_loop())

    def _build_environment(self) -> SandboxEnvironment:
        return SandboxEnvironment(
            spawner=AgentSpawner(
                arrival_rate_left=self.left_rate,
                arrival_rate_right=self.right_rate,
                distribution="poisson",
                seed=42,
            )
        )

    async def _simulation_loop(self) -> None:
        while self._running:
            with self._lock:
                self.env.spawner.set_arrival_rates(left=self.left_rate, right=self.right_rate)
            snapshot = await self.env.step_async(dt=0.2, decision_maker=self.decision_maker)
            self.peak_density_overall = max(self.peak_density_overall, snapshot.peak_density)
            self.snapshot_ready.emit(snapshot)
            if snapshot.frozen_this_step or snapshot.slow_brain_request_count:
                self.status_changed.emit(
                    f"slow-brain-window:req={snapshot.slow_brain_request_count}, frozen={snapshot.frozen_this_step}"
                )
            for log in snapshot.slow_brain_logs:
                self.all_slow_logs.append({
                    "step": log.step_index,
                    "agent": log.agent_id,
                    "density": log.density,
                    "action": log.action,
                    "rationale": log.rationale
                })
                self.log_received.emit(
                    f"[step={log.step_index:04d}] agent={log.agent_id:03d} density={log.density:.2f} "
                    f"action={log.action} :: {log.rationale}"
                )
            await asyncio.sleep(0.04)


class ZhiyanMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ZhiYan Agent | Linear Desktop")
        self.resize(1500, 900)
        self.setStyleSheet(LINEAR_QSS)

        self.bridge = AsyncSimulationBridge()
        self.bridge.snapshot_ready.connect(self._handle_snapshot)
        self.bridge.log_received.connect(self._append_log)
        self.bridge.status_changed.connect(self._append_status)
        self.bridge.report_ready.connect(self._show_report)

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header = self._build_header()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 6)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([320, 760, 360])

        root_layout.addWidget(header)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Zhiyan Agent")
        title.setObjectName("Title")
        subtitle = QLabel("Local crowd sandbox | Linear dark Bento UI")
        subtitle.setObjectName("Meta")
        badge = QLabel("RTX 5070 / Python 3.13.9")
        badge.setObjectName("Badge")

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        layout.addLayout(text_wrap)
        layout.addStretch(1)
        layout.addWidget(badge)
        return header

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Environment Boundary Panel")
        title.setObjectName("Title")
        meta = QLabel("Source: Itaewon incident parameters, Safety Science, GB50016")
        meta.setObjectName("Meta")

        self.left_rate_value = QLineEdit("2.5")
        self.left_rate_value.setReadOnly(True)
        self.right_rate_value = QLineEdit("2.5")
        self.right_rate_value.setReadOnly(True)
        self.left_slider = self._build_slider(5, 80, 25)
        self.right_slider = self._build_slider(5, 80, 25)
        self.left_slider.valueChanged.connect(self._sync_left_rate)
        self.right_slider.valueChanged.connect(self._sync_right_rate)

        self.peak_value = QLineEdit("0.00")
        self.peak_value.setReadOnly(True)
        self.active_value = QLineEdit("0")
        self.active_value.setReadOnly(True)
        self.local_density_value = QLineEdit("0.00")
        self.local_density_value.setReadOnly(True)
        self.slow_requests_value = QLineEdit("0")
        self.slow_requests_value.setReadOnly(True)
        self.freeze_status_value = QLineEdit("No")
        self.freeze_status_value.setReadOnly(True)
        self.mitigation_button = QPushButton("Show Mitigation")
        self.mitigation_button.setCheckable(True)
        self.mitigation_button.toggled.connect(self._toggle_mitigation_overlay)

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addLayout(self._metric_row("Left arrival (people/s)", self.left_rate_value))
        layout.addWidget(self.left_slider)
        layout.addLayout(self._metric_row("Right arrival (people/s)", self.right_rate_value))
        layout.addWidget(self.right_slider)
        layout.addSpacing(8)
        layout.addLayout(self._metric_row("Peak density", self.peak_value))
        layout.addLayout(self._metric_row("Active agents", self.active_value))
        layout.addLayout(self._metric_row("Max local density", self.local_density_value))
        layout.addLayout(self._metric_row("Slow-brain requests", self.slow_requests_value))
        layout.addLayout(self._metric_row("Physics frozen", self.freeze_status_value))

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("PrimaryButton")
        self.stop_button = QPushButton("Stop")
        self.start_button.clicked.connect(self.bridge.start)
        self.stop_button.clicked.connect(self.bridge.stop)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        self.report_button = QPushButton("Generate Diagnostic Report")
        self.report_button.clicked.connect(self._trigger_report)
        self.report_button.setEnabled(False)

        layout.addLayout(button_row)
        layout.addWidget(self.mitigation_button)
        layout.addWidget(self.report_button)
        layout.addStretch(1)
        return panel

    def _build_center_panel(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("CanvasCard")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Itaewon Floor-Plan Sandbox")
        title.setObjectName("Title")
        meta = QLabel("Floor-plan topology + subtle 2.5D stage + heatmap overlay")
        meta.setObjectName("Meta")
        self.canvas = SandboxCanvas()

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(self.canvas, 1)
        return wrapper

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.right_title = QLabel("Fast/Slow Brain Logs")
        self.right_title.setObjectName("Title")
        self.right_meta = QLabel("Monospace streaming panel for slow-brain decisions")
        self.right_meta.setObjectName("Meta")

        self.stack = QStackedWidget()

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Cascadia Code", 10))

        self.report_view = QTextBrowser()
        self.report_view.setReadOnly(True)
        self.report_view.setOpenExternalLinks(True)
        self.report_view.setStyleSheet("background: #17181a; color: #f7f8f8; border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 8px; padding: 12px 14px;")

        self.stack.addWidget(self.log_view)
        self.stack.addWidget(self.report_view)

        layout.addWidget(self.right_title)
        layout.addWidget(self.right_meta)
        layout.addWidget(self.stack, 1)
        return panel

    def _build_slider(self, minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)
        return slider

    def _metric_row(self, label_text: str, line_edit: QLineEdit) -> QHBoxLayout:
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("Meta")
        layout.addWidget(label, 1)
        layout.addWidget(line_edit)
        return layout

    @Slot()
    def _sync_left_rate(self) -> None:
        value = self.left_slider.value() / 10.0
        self.left_rate_value.setText(f"{value:.1f}")
        self.bridge.update_arrival_rates(value, self.right_slider.value() / 10.0)

    @Slot()
    def _sync_right_rate(self) -> None:
        value = self.right_slider.value() / 10.0
        self.right_rate_value.setText(f"{value:.1f}")
        self.bridge.update_arrival_rates(self.left_slider.value() / 10.0, value)

    @Slot(object)
    def _handle_snapshot(self, snapshot: SimulationSnapshot) -> None:
        self.peak_value.setText(f"{snapshot.peak_density:.2f}")
        self.active_value.setText(str(snapshot.active_agents))
        self.local_density_value.setText(f"{snapshot.max_local_density:.2f}")
        self.slow_requests_value.setText(str(snapshot.slow_brain_request_count))
        self.freeze_status_value.setText("Yes" if snapshot.frozen_this_step else "No")
        self.canvas.render_snapshot(snapshot, self.bridge.env)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    @Slot(str)
    def _append_status(self, message: str) -> None:
        self.log_view.appendPlainText(f"[status] {message}")
        if message == "simulation-stopped":
            self.report_button.setEnabled(True)
        elif message == "simulation-started":
            self.report_button.setEnabled(False)
            self.right_title.setText("Fast/Slow Brain Logs")
            self.right_meta.setText("Monospace streaming panel for slow-brain decisions")
            self.stack.setCurrentIndex(0)
            self.log_view.clear()

    @Slot()
    def _trigger_report(self) -> None:
        self.right_title.setText("RAG Diagnostic Report")
        self.right_meta.setText("Retrieval-Augmented Generation based on simulation logs")
        self.stack.setCurrentIndex(1)
        self.report_view.setMarkdown("## Generating report...\n\nPlease wait while local RAG pipeline retrieves relevant safety codes and runs LLM inference.")
        self.bridge.generate_report()

    @Slot(str)
    def _show_report(self, markdown_text: str) -> None:
        self.report_view.setMarkdown(markdown_text)

    @Slot(bool)
    def _toggle_mitigation_overlay(self, enabled: bool) -> None:
        self.canvas.set_mitigation_visible(enabled)
        self.mitigation_button.setText("Hide Mitigation" if enabled else "Show Mitigation")


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
