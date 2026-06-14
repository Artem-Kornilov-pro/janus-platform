from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner
from graph_layout import build_graph_elements, circular_layout

NODE_RADIUS = 28


class GraphTab(QWidget):
    """Visualize the knowledge graph as a node/edge diagram."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}

        self.refresh_button = QPushButton("Обновить граф")
        self.refresh_button.clicked.connect(self.refresh)

        self.status_label = QLabel("Нажмите «Обновить граф», чтобы загрузить данные")

        top_row = QHBoxLayout()
        top_row.addWidget(self.refresh_button)
        top_row.addWidget(self.status_label)
        top_row.addStretch(1)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.view)
        self.setLayout(layout)

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

    def _draw(self, nodes: dict[str, dict], edges: list[dict]) -> None:
        self.scene.clear()

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
            self.scene.addItem(ellipse)

            text = QGraphicsSimpleTextItem(node["display"])
            text.setFont(label_font)
            text.setBrush(QBrush(QColor("#1e1f26")))
            text_rect = text.boundingRect()
            text.setPos(x - text_rect.width() / 2, y - text_rect.height() / 2)
            self.scene.addItem(text)

        self.view.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        self.view.fitInView(self.view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
