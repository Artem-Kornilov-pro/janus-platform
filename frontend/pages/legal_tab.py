from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner
from export_utils import rows_to_csv

_SEVERITY_COLORS = {"high": "#ff6b6b", "medium": "#ffb84d", "low": "#4dd0a1"}

_RISK_COLS = ["severity", "risk", "clause_title", "document_title"]
_OBL_COLS = ["obligated_party", "obligation", "beneficiary_party"]
_DEAD_COLS = ["date", "type", "description", "bound_party", "clause_title", "document_title"]


# ---------------------------------------------------------------------------
# Reusable table widget with CSV export
# ---------------------------------------------------------------------------

class _ReportTable(QWidget):
    def __init__(self, columns: list[str], load_label: str, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._columns = columns
        self._pending: dict[str, str] = {}

        self.load_button = QPushButton(load_label)
        self.export_button = QPushButton("Экспорт в CSV")
        self.status_label = QLabel(f"Нажмите «{load_label}»")

        top_row = QHBoxLayout()
        top_row.addWidget(self.load_button)
        top_row.addWidget(self.export_button)
        top_row.addWidget(self.status_label)
        top_row.addStretch(1)

        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.export_button.clicked.connect(self._export_csv)
        self._runner.finished.connect(self._on_finished)

    def _populate(self, rows: list[dict]) -> None:
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, col in enumerate(self._columns):
                value = row.get(col)
                text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                # Colour-code severity column for risk table.
                if col == "severity" and text in _SEVERITY_COLORS:
                    item.setForeground(QColor(_SEVERITY_COLORS[text]))
                self.table.setItem(row_idx, col_idx, item)

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind != "load":
            return
        self.load_button.setEnabled(True)
        if error is not None:
            self.status_label.setText(f"Ошибка: {error}")
            return
        rows = result if isinstance(result, list) else ([result] if result else [])
        self._populate(rows)
        self.status_label.setText(f"Записей: {len(rows)}")

    def _export_csv(self) -> None:
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Экспорт", "Нет данных для экспорта.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как CSV", "", "CSV files (*.csv)")
        if not path:
            return
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "")
            rows.append(row)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(rows_to_csv(self._columns, rows))
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")


# ---------------------------------------------------------------------------
# Sub-tab: Risk report
# ---------------------------------------------------------------------------

class _RiskTab(_ReportTable):
    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__(_RISK_COLS, "Загрузить риски", runner)
        self.load_button.clicked.connect(self._load)

    def _load(self) -> None:
        self.load_button.setEnabled(False)
        self.status_label.setText("Загрузка...")
        call_id = self._runner.submit(lambda: mcp_client.get_risk_report())
        self._pending[call_id] = "load"


# ---------------------------------------------------------------------------
# Sub-tab: Obligations by party
# ---------------------------------------------------------------------------

class _ObligationsTab(_ReportTable):
    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__(_OBL_COLS, "Найти обязательства", runner)

        self.party_input = QLineEdit()
        self.party_input.setPlaceholderText("Название стороны (или * для всех)")
        self.party_input.returnPressed.connect(self._load)

        top_layout = self.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel("Сторона:"))
        row.addWidget(self.party_input)
        top_layout.insertLayout(0, row)

        self.load_button.clicked.connect(self._load)

    def _load(self) -> None:
        name = self.party_input.text().strip() or "*"
        self.load_button.setEnabled(False)
        self.status_label.setText("Поиск...")
        call_id = self._runner.submit(lambda: mcp_client.get_obligations_by_party(name))
        self._pending[call_id] = "load"


# ---------------------------------------------------------------------------
# Sub-tab: Deadlines
# ---------------------------------------------------------------------------

class _DeadlinesTab(_ReportTable):
    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__(_DEAD_COLS, "Загрузить сроки", runner)

        self.overdue_check = QCheckBox("Только просроченные")
        self.load_button.layout() if False else None

        btn_row: QHBoxLayout = self.layout().itemAt(0).layout()  # type: ignore[union-attr]
        btn_row.insertWidget(1, self.overdue_check)

        self.load_button.clicked.connect(self._load)

    def _load(self) -> None:
        overdue = self.overdue_check.isChecked()
        self.load_button.setEnabled(False)
        self.status_label.setText("Загрузка...")
        call_id = self._runner.submit(lambda: mcp_client.get_deadlines(overdue))
        self._pending[call_id] = "load"


# ---------------------------------------------------------------------------
# Main LegalTab
# ---------------------------------------------------------------------------

class LegalTab(QWidget):
    """Legal-domain tools: risk report, obligations by party, deadlines tracker."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()

        tabs = QTabWidget()
        tabs.addTab(_RiskTab(runner), "Риски")
        tabs.addTab(_ObligationsTab(runner), "Обязательства")
        tabs.addTab(_DeadlinesTab(runner), "Сроки")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)
