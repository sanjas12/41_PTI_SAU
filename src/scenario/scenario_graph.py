from typing import Dict, Optional

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
)

from .scenario_model import (
    TRIGGER_ALL,
    TRIGGER_ANY,
    Scenario,
    ScenarioConnection,
    ScenarioStep,
)

NODE_WIDTH = 210.0
NODE_HEIGHT = 144.0
SOCKET_RADIUS = 7.0


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
        return QRectF(-SOCKET_RADIUS, 0.0, NODE_WIDTH + 2 * SOCKET_RADIUS, NODE_HEIGHT)

    def input_position(self) -> QPointF:
        return self.mapToScene(QPointF(0.0, NODE_HEIGHT / 2))

    def output_position(self) -> QPointF:
        return self.mapToScene(QPointF(NODE_WIDTH, NODE_HEIGHT / 2))

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(0.0, 0.0, NODE_WIDTH, NODE_HEIGHT)
        border = QColor("#69a7ff") if self.isSelected() else QColor("#4b5262")
        painter.setPen(QPen(border, 2.0 if self.isSelected() else 1.0))
        painter.setBrush(QBrush(QColor("#292d35")))
        painter.drawRoundedRect(body, 7.0, 7.0)

        header = QRectF(0.0, 0.0, NODE_WIDTH, 31.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#315f4a")))
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
        details = (
            f"Канал {self.step.channel_id + 1}  ·  {self.step.signal_type}\n"
            f"Длительность: {self.step.duration:g} с\n"
            f"A: {self.step.amplitude:g} %   f: {self.step.frequency:g} Гц\n"
            f"Смещение: {self.step.offset:g} %{trigger_text}"
        )
        painter.drawText(QRectF(13.0, 39.0, 185.0, 96.0), Qt.AlignLeft, details)

        painter.setPen(QPen(QColor("#15171b"), 1.0))
        painter.setBrush(QBrush(QColor("#69a7ff")))
        painter.drawEllipse(QPointF(0.0, NODE_HEIGHT / 2), SOCKET_RADIUS, SOCKET_RADIUS)
        painter.setBrush(QBrush(QColor("#55b879")))
        painter.drawEllipse(
            QPointF(NODE_WIDTH, NODE_HEIGHT / 2), SOCKET_RADIUS, SOCKET_RADIUS
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
            output = QPointF(NODE_WIDTH, NODE_HEIGHT / 2)
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-2000.0, -1200.0, 4000.0, 2400.0)
        self.nodes: Dict[str, StepNodeItem] = {}
        self.connections: Dict[ScenarioConnection, ConnectionItem] = {}
        self.connection_source: Optional[StepNodeItem] = None
        self.preview: Optional[QGraphicsPathItem] = None
        self.scenario: Optional[Scenario] = None

    def set_scenario(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.clear()
        self.nodes.clear()
        self.connections.clear()
        labels = scenario.get_step_labels()
        for step in scenario.steps:
            node = StepNodeItem(self, step, labels[step.id])
            self.nodes[step.id] = node
            self.addItem(node)
        for connection in scenario.connections:
            source = self.nodes.get(connection.source_id)
            target = self.nodes.get(connection.target_id)
            if source and target:
                item = ConnectionItem(source, target)
                self.connections[connection] = item
                self.addItem(item)

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


class ScenarioGraphView(QGraphicsView):
    """Рабочее поле со сглаживанием, масштабированием и сеткой."""

    def __init__(self, scene: ScenarioGraphScene, parent=None):
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
