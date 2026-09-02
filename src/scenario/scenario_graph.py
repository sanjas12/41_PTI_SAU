from typing import Dict, Optional

from PyQt5.QtCore import QObject, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from core.signal_types import SignalType

from .scenario_model import (
    TRIGGER_ALL,
    TRIGGER_ANY,
    Scenario,
    ScenarioConnection,
    ScenarioStep,
)

NODE_WIDTH = 210.0
NODE_HEIGHT = 144.0
NODE_HEIGHT_WITH_TRIGGER = 166.0
SOCKET_RADIUS = 7.0
ANALOG_HEADER_COLOR = QColor("#315f4a")
DISCRETE_HEADER_COLOR = QColor("#4f5f9f")


def node_header_color(signal_type_name: str) -> QColor:
    """Вернуть цвет заголовка для аналогового или дискретного шага."""
    signal_type = SignalType[signal_type_name.upper()]
    if signal_type.is_discrete():
        return DISCRETE_HEADER_COLOR
    return ANALOG_HEADER_COLOR


class ConnectionItem(QGraphicsPathItem):
    """Кривая направленная связь между двумя блоками."""

    def __init__(self, source: "StepNodeItem", target: "StepNodeItem"):
        super().__init__()
        self.source = source
        self.target = target
        self.arrow = QGraphicsPolygonItem(self)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1)
        self.setPen(QPen(QColor("#55b879"), 2.5))
        self.arrow.setBrush(QBrush(QColor("#55b879")))
        self.arrow.setPen(QPen(Qt.NoPen))
        self.update_path()

    def update_path(self) -> None:
        start = self.source.output_position()
        end = self.target.input_position()
        distance = max(70.0, abs(end.x() - start.x()) * 0.55)
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + distance, start.y()),
            QPointF(end.x() - distance, end.y()),
            end,
        )
        self.setPath(path)
        self.arrow.setPolygon(
            QPolygonF(
                [
                    end,
                    QPointF(end.x() - 11.0, end.y() - 6.0),
                    QPointF(end.x() - 11.0, end.y() + 6.0),
                ]
            )
        )


class StepNodeItem(QGraphicsItem):
    """Перемещаемый блок шага с входным и выходным портами."""

    def __init__(self, scene: "ScenarioGraphScene", step: ScenarioStep, number: str):
        super().__init__()
        self.graph_scene = scene
        self.step = step
        self.number = number
        incoming_count = 0
        if scene.scenario:
            incoming_count = len(scene.scenario.incoming_ids(step.id))
        self.node_height = (
            NODE_HEIGHT_WITH_TRIGGER if incoming_count > 1 else NODE_HEIGHT
        )
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setPos(step.position_x, step.position_y)
        self.setToolTip(
            "Перетащите блок для перемещения. Двойной щелчок — редактирование.\n"
            "Протяните связь от зелёного выхода к синему входу другого блока."
        )

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(
            -SOCKET_RADIUS,
            0.0,
            NODE_WIDTH + 2 * SOCKET_RADIUS,
            self.node_height,
        )

    def input_position(self) -> QPointF:
        return self.mapToScene(QPointF(0.0, self.node_height / 2))

    def output_position(self) -> QPointF:
        return self.mapToScene(QPointF(NODE_WIDTH, self.node_height / 2))

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(0.0, 0.0, NODE_WIDTH, self.node_height)
        border = QColor("#69a7ff") if self.isSelected() else QColor("#4b5262")
        painter.setPen(QPen(border, 2.0 if self.isSelected() else 1.0))
        painter.setBrush(QBrush(QColor("#292d35")))
        painter.drawRoundedRect(body, 7.0, 7.0)

        header = QRectF(0.0, 0.0, NODE_WIDTH, 31.0)
        painter.setPen(Qt.NoPen)
        signal_type = SignalType[self.step.signal_type.upper()]
        painter.setBrush(QBrush(node_header_color(self.step.signal_type)))
        painter.drawRoundedRect(header, 7.0, 7.0)
        painter.drawRect(QRectF(0.0, 22.0, NODE_WIDTH, 9.0))

        painter.setPen(QColor("#f1f3f5"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(
            QRectF(12.0, 5.0, 185.0, 22.0), Qt.AlignVCenter, f"Шаг {self.number}"
        )

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#e4e7eb"))
        incoming_count = 0
        if self.graph_scene.scenario:
            incoming_count = len(self.graph_scene.scenario.incoming_ids(self.step.id))
        trigger_text = ""
        if incoming_count > 1:
            if self.step.trigger_mode == TRIGGER_ANY:
                trigger_text = "\nСтарт: после любого входа"
            elif self.step.trigger_mode == TRIGGER_ALL:
                trigger_text = "\nСтарт: после всех входов"
            else:
                trigger_text = "\nСтарт: после выбранного входа"
        if signal_type.is_discrete():
            parameter_text = f"Частота: {self.step.frequency:g} Гц"
            if signal_type == SignalType.PWM:
                parameter_text += f"   Заполнение: {self.step.duty_cycle:g} %"
            elif signal_type == SignalType.PULSE:
                parameter_text += f"   Импульс: {self.step.pulse_width:g} с"
            details = (
                f"Канал {self.step.channel_id + 1}  ·  {signal_type}\n"
                f"Длительность: {self.step.duration:g} с\n"
                f"{parameter_text}\n"
                f"Состояния: ВЫКЛ / ВКЛ{trigger_text}"
            )
        else:
            details = (
                f"Канал {self.step.channel_id + 1}  ·  {signal_type}\n"
                f"Длительность: {self.step.duration:g} с\n"
                f"A: {self.step.amplitude:g} %   f: {self.step.frequency:g} Гц\n"
                f"Смещение: {self.step.offset:g} %{trigger_text}"
            )
        painter.drawText(
            QRectF(13.0, 39.0, 185.0, self.node_height - 48.0),
            Qt.AlignLeft,
            details,
        )

        painter.setPen(QPen(QColor("#15171b"), 1.0))
        painter.setBrush(QBrush(QColor("#69a7ff")))
        painter.drawEllipse(
            QPointF(0.0, self.node_height / 2), SOCKET_RADIUS, SOCKET_RADIUS
        )
        painter.setBrush(QBrush(QColor("#55b879")))
        painter.drawEllipse(
            QPointF(NODE_WIDTH, self.node_height / 2), SOCKET_RADIUS, SOCKET_RADIUS
        )

    def itemChange(self, change, value):  # noqa: N802
        result = super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.step.position_x = self.pos().x()
            self.step.position_y = self.pos().y()
            self.graph_scene.update_connections(self)
            self.graph_scene.graph_changed.emit()
        return result

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            local = event.pos()
            output = QPointF(NODE_WIDTH, self.node_height / 2)
            if abs(local.x() - output.x()) <= 14 and abs(local.y() - output.y()) <= 14:
                self.graph_scene.begin_connection(self)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.graph_scene.edit_requested.emit(self.step.id)
        event.accept()


class ScenarioGraphScene(QGraphicsScene):
    """Сцена графа и интерактивное создание связей."""

    edit_requested = pyqtSignal(str)
    connection_requested = pyqtSignal(str, str)
    graph_changed = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setSceneRect(-2000.0, -1200.0, 4000.0, 2400.0)
        self.nodes: Dict[str, StepNodeItem] = {}
        self.connections: Dict[ScenarioConnection, ConnectionItem] = {}
        self.duration_bars: Dict[str, QGraphicsRectItem] = {}
        self.connection_source: Optional[StepNodeItem] = None
        self.preview: Optional[QGraphicsPathItem] = None
        self.scenario: Optional[Scenario] = None
        self.playhead_progress = 0.0
        self.playhead_time = 0.0
        self.playhead_line: Optional[QGraphicsLineItem] = None
        self.playhead_label: Optional[QGraphicsSimpleTextItem] = None

    def set_scenario(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.clear()
        self.nodes.clear()
        self.connections.clear()
        self.duration_bars.clear()
        labels = scenario.get_step_labels()
        for step in scenario.steps:
            node = StepNodeItem(self, step, labels[step.id])
            self.nodes[step.id] = node
            self.addItem(node)
        self._create_duration_bars()
        for connection in scenario.connections:
            source = self.nodes.get(connection.source_id)
            target = self.nodes.get(connection.target_id)
            if source and target:
                item = ConnectionItem(source, target)
                self.connections[connection] = item
                self.addItem(item)
        self._create_playhead()

    def _create_duration_bars(self) -> None:
        """Добавить под блоками полосы, по которым движется указатель времени."""
        for step in self.scenario.steps if self.scenario else []:
            node = self.nodes[step.id]
            color = node_header_color(step.signal_type)
            color.setAlpha(190)
            bar = QGraphicsRectItem(
                QRectF(
                    node.pos().x(),
                    node.pos().y() + node.node_height + 7.0,
                    NODE_WIDTH,
                    7.0,
                )
            )
            bar.setPen(QPen(Qt.NoPen))
            bar.setBrush(QBrush(color))
            bar.setZValue(-0.5)
            bar.setAcceptedMouseButtons(Qt.NoButton)
            self.duration_bars[step.id] = bar
            self.addItem(bar)

    def _create_playhead(self) -> None:
        """Создать вертикальный указатель текущего момента сценария."""
        self.playhead_line = QGraphicsLineItem()
        self.playhead_line.setPen(QPen(QColor("#ffb347"), 2.0, Qt.DashLine))
        self.playhead_line.setZValue(10.0)
        self.playhead_line.setAcceptedMouseButtons(Qt.NoButton)
        self.addItem(self.playhead_line)

        self.playhead_label = QGraphicsSimpleTextItem()
        self.playhead_label.setBrush(QBrush(QColor("#ffcf87")))
        self.playhead_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.playhead_label.setZValue(10.0)
        self.playhead_label.setAcceptedMouseButtons(Qt.NoButton)
        self.addItem(self.playhead_label)
        self._update_playhead()

    def set_playhead(self, progress: float, elapsed_seconds: float) -> None:
        """Переместить указатель согласно прогрессу выполнения сценария."""
        self.playhead_progress = max(0.0, min(100.0, progress))
        self.playhead_time = max(0.0, elapsed_seconds)
        self._update_playhead()

    def _update_playhead(self) -> None:
        if not self.playhead_line or not self.playhead_label or not self.nodes:
            if self.playhead_line:
                self.playhead_line.hide()
            if self.playhead_label:
                self.playhead_label.hide()
            return

        top = min(node.pos().y() for node in self.nodes.values()) - 34.0
        bottom = (
            max(node.pos().y() + node.node_height for node in self.nodes.values())
            + 20.0
        )
        x = self._playhead_x()

        self.playhead_line.setLine(x, top, x, bottom)
        self.playhead_line.show()
        minutes, seconds = divmod(int(self.playhead_time), 60)
        hours, minutes = divmod(minutes, 60)
        time_text = (
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes:02d}:{seconds:02d}"
        )
        self.playhead_label.setText(time_text)
        self.playhead_label.setPos(x + 5.0, top - 2.0)
        self.playhead_label.show()

    def _playhead_x(self) -> float:
        """Вычислить положение линии внутри выполняемых в данный момент шагов."""
        if not self.scenario:
            return 0.0
        timings = self.scenario.get_step_timings()
        total_duration = self.scenario.get_total_duration()
        elapsed = min(self.playhead_time, total_duration)
        if elapsed <= 0.0:
            return min(node.pos().x() for node in self.nodes.values())
        positions = []
        for step in self.scenario.steps:
            start_time, finish_time = timings[step.id]
            is_active = start_time <= elapsed < finish_time
            if elapsed == total_duration and finish_time == total_duration:
                is_active = True
            if not is_active:
                continue
            duration = max(step.duration, 0.001)
            step_progress = min(1.0, max(0.0, (elapsed - start_time) / duration))
            positions.append(self.nodes[step.id].pos().x() + NODE_WIDTH * step_progress)
        if positions:
            return sum(positions) / len(positions)
        return min(node.pos().x() for node in self.nodes.values())

    def begin_connection(self, source: StepNodeItem) -> None:
        self.connection_source = source
        self.preview = QGraphicsPathItem()
        self.preview.setPen(QPen(QColor("#8bd5a5"), 2.0, Qt.DashLine))
        self.addItem(self.preview)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.connection_source and self.preview:
            start = self.connection_source.output_position()
            end = event.scenePos()
            path = QPainterPath(start)
            distance = max(70.0, abs(end.x() - start.x()) * 0.55)
            path.cubicTo(
                QPointF(start.x() + distance, start.y()),
                QPointF(end.x() - distance, end.y()),
                end,
            )
            self.preview.setPath(path)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.connection_source:
            target = self._node_at_input(event.scenePos())
            source = self.connection_source
            if self.preview:
                self.removeItem(self.preview)
            self.preview = None
            self.connection_source = None
            if target and target is not source:
                self.connection_requested.emit(source.step.id, target.step.id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _node_at_input(self, position: QPointF) -> Optional[StepNodeItem]:
        for node in self.nodes.values():
            point = node.input_position()
            if (
                abs(position.x() - point.x()) <= 18
                and abs(position.y() - point.y()) <= 18
            ):
                return node
        return None

    def update_connections(self, node: StepNodeItem) -> None:
        for item in self.connections.values():
            if item.source is node or item.target is node:
                item.update_path()
        duration_bar = self.duration_bars.get(node.step.id)
        if duration_bar:
            rect = duration_bar.rect()
            rect.moveTo(node.pos().x(), node.pos().y() + node.node_height + 7.0)
            duration_bar.setRect(rect)
        self._update_playhead()


class ScenarioGraphView(QGraphicsView):
    """Рабочее поле со сглаживанием, масштабированием и сеткой."""

    def __init__(
        self, scene: ScenarioGraphScene, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#1c1f24")))
        self.setMinimumHeight(180)

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = self.transform().m11()
        if 0.35 <= current * factor <= 2.5:
            self.scale(factor, factor)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor("#2c3038"), 1.0))
        spacing = 24
        left = int(rect.left()) - int(rect.left()) % spacing
        top = int(rect.top()) - int(rect.top()) % spacing
        x = left
        while x < rect.right():
            y = top
            while y < rect.bottom():
                painter.drawPoint(x, y)
                y += spacing
            x += spacing
