from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner


class LearningTab(QWidget):
    """Submit human feedback on extracted entities and view Learning Brain stats."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}

        self.document_id_input = QLineEdit()
        self.clause_id_input = QLineEdit()
        self.entity_id_input = QLineEdit()
        self.entity_type_input = QLineEdit()
        self.original_value_input = QLineEdit()
        self.corrected_value_input = QLineEdit()
        self.is_correct_checkbox = QCheckBox("Извлечение верно")

        form = QFormLayout()
        form.addRow("ID документа", self.document_id_input)
        form.addRow("ID пункта (clause)", self.clause_id_input)
        form.addRow("ID сущности", self.entity_id_input)
        form.addRow("Тип сущности", self.entity_type_input)
        form.addRow("Исходное значение", self.original_value_input)
        form.addRow("Исправленное значение", self.corrected_value_input)
        form.addRow("", self.is_correct_checkbox)

        self.submit_button = QPushButton("Отправить отзыв")
        self.submit_button.clicked.connect(self._submit_feedback)

        self.refresh_stats_button = QPushButton("Обновить статистику")
        self.refresh_stats_button.clicked.connect(self.refresh_stats)

        button_row = QHBoxLayout()
        button_row.addWidget(self.submit_button)
        button_row.addWidget(self.refresh_stats_button)

        self.stats_table = QTableWidget()

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addWidget(self.stats_table)
        layout.addWidget(self.log_box)
        self.setLayout(layout)

        self._runner.finished.connect(self._on_finished)
        self.refresh_stats()

    def _submit_feedback(self) -> None:
        corrected = self.corrected_value_input.text().strip() or None
        self.submit_button.setEnabled(False)

        call_id = self._runner.submit(
            lambda: mcp_client.submit_feedback(
                document_id=self.document_id_input.text().strip(),
                clause_id=self.clause_id_input.text().strip(),
                entity_id=self.entity_id_input.text().strip(),
                entity_type=self.entity_type_input.text().strip(),
                original_value=self.original_value_input.text().strip(),
                is_correct=self.is_correct_checkbox.isChecked(),
                corrected_value=corrected,
            )
        )
        self._pending[call_id] = "feedback"

    def refresh_stats(self) -> None:
        self.refresh_stats_button.setEnabled(False)
        call_id = self._runner.submit(mcp_client.get_learning_stats)
        self._pending[call_id] = "stats"

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind is None:
            return

        if kind == "feedback":
            self.submit_button.setEnabled(True)
            if error is not None:
                self.log_box.append(f"Ошибка отправки отзыва: {error}")
                return
            self.log_box.append(f"Отзыв сохранён: {json.dumps(result, ensure_ascii=False)}")
            self.refresh_stats()

        elif kind == "stats":
            self.refresh_stats_button.setEnabled(True)
            if error is not None:
                self.log_box.append(f"Ошибка загрузки статистики: {error}")
                return
            self._populate_stats(result or {})

    def _populate_stats(self, stats: dict) -> None:
        by_type = stats.get("by_entity_type", {})
        columns = ["entity_type", "total", "correct", "incorrect", "precision", "reward"]

        self.stats_table.clear()
        self.stats_table.setColumnCount(len(columns))
        self.stats_table.setHorizontalHeaderLabels(columns)
        self.stats_table.setRowCount(len(by_type))

        for row_idx, (entity_type, values) in enumerate(by_type.items()):
            row = {"entity_type": entity_type, **values}
            for col_idx, col in enumerate(columns):
                self.stats_table.setItem(row_idx, col_idx, QTableWidgetItem(str(row.get(col, ""))))

        self.log_box.append(f"Всего отзывов: {stats.get('total_feedback', 0)}")
