from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner
from export_utils import rows_to_csv

ENTITY_LABELS = ["Party", "Obligation", "Risk", "LegalNorm", "Invoice", "Deadline", "Claim"]


class EntitiesTab(QWidget):
    """Search entities by label/name and inspect their relationships."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}

        self.label_combo = QComboBox()
        self.label_combo.addItems(ENTITY_LABELS)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Имя/название (необязательно)")
        self.name_input.returnPressed.connect(self._search)

        self.search_button = QPushButton("Поиск")
        self.search_button.clicked.connect(self._search)

        self.export_button = QPushButton("Экспорт в CSV")
        self.export_button.clicked.connect(self._export_csv)

        search_row = QHBoxLayout()
        search_row.addWidget(self.label_combo)
        search_row.addWidget(self.name_input)
        search_row.addWidget(self.search_button)
        search_row.addWidget(self.export_button)

        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.itemDoubleClicked.connect(self._show_relationships)

        self.relationships_box = QTextEdit()
        self.relationships_box.setReadOnly(True)
        self.relationships_box.setPlaceholderText(
            "Дважды кликните по строке, чтобы посмотреть связи сущности"
        )

        layout = QVBoxLayout()
        layout.addLayout(search_row)
        layout.addWidget(self.table)
        layout.addWidget(self.relationships_box)
        self.setLayout(layout)

        self._runner.finished.connect(self._on_finished)

    def _search(self) -> None:
        label = self.label_combo.currentText()
        name = self.name_input.text().strip() or "*"

        self.search_button.setEnabled(False)
        call_id = self._runner.submit(lambda: mcp_client.get_entity_by_label(label, name))
        self._pending[call_id] = "search"

    def _export_csv(self) -> None:
        if self.table.rowCount() == 0 or self.table.columnCount() == 0:
            QMessageBox.information(self, "Экспорт в CSV", "Нет данных для экспорта. Сначала выполните поиск.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как CSV", "", "CSV files (*.csv)")
        if not path:
            return

        columns = [
            self.table.horizontalHeaderItem(col).text() for col in range(self.table.columnCount())
        ]
        rows = []
        for row_idx in range(self.table.rowCount()):
            row = []
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(row_idx, col_idx)
                row.append(item.text() if item is not None else "")
            rows.append(row)

        csv_text = rows_to_csv(columns, rows)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(csv_text)

        QMessageBox.information(self, "Экспорт в CSV", f"Сохранено: {path}")

    def _show_relationships(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return

        entity_name = None
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col).text()
            if header in ("name", "title", "id", "code"):
                item = self.table.item(row, col)
                if item is not None:
                    entity_name = item.text()
                    break

        if not entity_name:
            return

        self.relationships_box.append(f"Связи для: {entity_name}...")
        call_id = self._runner.submit(lambda: mcp_client.find_relationships(entity_name, "*"))
        self._pending[call_id] = "relationships"

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind is None:
            return

        if kind == "search":
            self.search_button.setEnabled(True)
            if error is not None:
                self.relationships_box.append(f"Ошибка поиска: {error}")
                return
            self._populate_table(result or [])

        elif kind == "relationships":
            if error is not None:
                self.relationships_box.append(f"Ошибка: {error}")
                return
            self.relationships_box.append(json.dumps(result, ensure_ascii=False, indent=2))

    def _populate_table(self, rows: list[dict]) -> None:
        self.table.clear()
        if not rows:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        columns = sorted({key for row in rows for key in row.keys()})
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(rows))

        for row_idx, row in enumerate(rows):
            for col_idx, col in enumerate(columns):
                value = row.get(col, "")
                if not isinstance(value, str):
                    value = json.dumps(value, ensure_ascii=False)
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
