from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner
from graph_layout import build_graph_elements, circular_layout, describe_node_connections

NODE_RADIUS = 28
ZOOM_FACTOR = 1.25
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


class ZoomableGraphView(QGraphicsView):
    """QGraphicsView with mouse-wheel and button-driven zoom."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._zoom = 1.0

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def zoom_in(self) -> None:
        self._apply_zoom(ZOOM_FACTOR)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / ZOOM_FACTOR)

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = self._zoom * factor
        if new_zoom < MIN_ZOOM or new_zoom > MAX_ZOOM:
            return
        self._zoom = new_zoom
        self.scale(factor, factor)

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self.resetTransform()
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class GraphTab(QWidget):
    """Visualize the knowledge graph as a node/edge diagram."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}
        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = []

        self.refresh_button = QPushButton("Обновить граф")
        self.refresh_button.clicked.connect(self.refresh)

        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setFixedWidth(32)
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setFixedWidth(32)
        self.zoom_reset_button = QPushButton("100%")

        self.status_label = QLabel("Нажмите «Обновить граф», чтобы загрузить данные")

        top_row = QHBoxLayout()
        top_row.addWidget(self.refresh_button)
        top_row.addWidget(self.zoom_in_button)
        top_row.addWidget(self.zoom_out_button)
        top_row.addWidget(self.zoom_reset_button)
        top_row.addWidget(self.status_label)
        top_row.addStretch(1)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphView(self.scene)

        self.zoom_in_button.clicked.connect(self.view.zoom_in)
        self.zoom_out_button.clicked.connect(self.view.zoom_out)
        self.zoom_reset_button.clicked.connect(self.view.reset_zoom)

        self.info_panel = QTextEdit()
        self.info_panel.setReadOnly(True)
        self.info_panel.setPlaceholderText("Нажмите на узел графа, чтобы увидеть информацию о нём")
        self.info_panel.setFixedHeight(120)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.view)
        layout.addWidget(self.info_panel)
        self.setLayout(layout)

        self.scene.selectionChanged.connect(self._on_node_selected)
        self._runner.finished.connect(self._on_finished)

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        self.status_label.setText("Загрузка графа...")
        call_id = self._runner.submit(lambda: mcp_client.find_relationships("*", "*"))
        self._pending[call_id] = "graph"

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind != "graph":
            return

        self.refresh_button.setEnabled(True)

        if error is not None:
            self.status_label.setText(f"Ошибка загрузки графа: {error}")
            return

        relationships = result or []
        nodes, edges = build_graph_elements(relationships)
        self._draw(nodes, edges)
        self.status_label.setText(f"Узлов: {len(nodes)}, связей: {len(edges)}")

    def _on_node_selected(self) -> None:
        items = self.scene.selectedItems()
        if not items:
            return
        key = items[0].data(0)
        if key is None:
            return
        self.info_panel.setPlainText(describe_node_connections(key, self._nodes, self._edges))

    def _draw(self, nodes: dict[str, dict], edges: list[dict]) -> None:
        self.scene.clear()
        self._nodes = nodes
        self._edges = edges
        self.info_panel.clear()

        if not nodes:
            self.scene.addText("Граф пуст")
            return

        node_keys = list(nodes.keys())
        radius = max(150.0, 60.0 * len(node_keys))
        positions = circular_layout(node_keys, radius=radius)

        label_font = QFont()
        label_font.setPointSize(8)

        # Draw edges first so nodes render on top.
        for edge in edges:
            src_pos = positions.get(edge["source"])
            dst_pos = positions.get(edge["target"])
            if src_pos is None or dst_pos is None:
                continue

            line = QGraphicsLineItem(src_pos[0], src_pos[1], dst_pos[0], dst_pos[1])
            line.setPen(QPen(QColor("#4a4d5a"), 1.5))
            self.scene.addItem(line)

            mid_x = (src_pos[0] + dst_pos[0]) / 2
            mid_y = (src_pos[1] + dst_pos[1]) / 2
            edge_label = QGraphicsSimpleTextItem(edge["label"])
            edge_label.setFont(label_font)
            edge_label.setBrush(QBrush(QColor("#9a9dab")))
            edge_label.setPos(mid_x, mid_y)
            self.scene.addItem(edge_label)

        # Draw nodes on top of edges.
        for key, node in nodes.items():
            x, y = positions[key]

            ellipse = QGraphicsEllipseItem(
                x - NODE_RADIUS, y - NODE_RADIUS, NODE_RADIUS * 2, NODE_RADIUS * 2
            )
            ellipse.setBrush(QBrush(QColor(node["color"])))
            ellipse.setPen(QPen(QColor("#1e1f26"), 2))
            ellipse.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            ellipse.setData(0, key)
            self.scene.addItem(ellipse)

            text = QGraphicsSimpleTextItem(node["display"])
            text.setFont(label_font)
            text.setBrush(QBrush(QColor("#1e1f26")))
            text_rect = text.boundingRect()
            text.setPos(x - text_rect.width() / 2, y - text_rect.height() / 2)
            self.scene.addItem(text)

        self.view.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        self.view.reset_zoom()
