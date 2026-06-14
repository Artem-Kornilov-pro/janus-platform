from __future__ import annotations

import sys
from pathlib import Path

if (project_root := str(Path(__file__).resolve().parents[2])) not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner
from domains.finance.tax_calculator import VAT_RATES, simplified_tax, vat_from_gross, vat_from_net
from export_utils import rows_to_csv

INVOICE_COLUMNS = ["number", "amount", "currency", "vat_rate", "due_date", "issuer", "payer"]


class FinanceTab(QWidget):
    """Quick calculators and reports for everyday finance/accounting tasks."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}

        # --- VAT calculator -------------------------------------------------
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 1_000_000_000)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(1000)

        self.rate_combo = QComboBox()
        self.rate_combo.addItems([f"{rate}%" for rate in VAT_RATES])
        self.rate_combo.setCurrentIndex(len(VAT_RATES) - 1)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Сумма без НДС", "Сумма с НДС"])

        self.vat_button = QPushButton("Рассчитать")
        self.vat_button.clicked.connect(self._calc_vat)

        self.vat_result = QLabel("-")

        vat_form = QFormLayout()
        vat_form.addRow("Сумма:", self.amount_input)
        vat_form.addRow("Ставка НДС:", self.rate_combo)
        vat_form.addRow("Сумма указана как:", self.mode_combo)

        vat_layout = QVBoxLayout()
        vat_layout.addLayout(vat_form)
        vat_button_row = QHBoxLayout()
        vat_button_row.addWidget(self.vat_button)
        vat_button_row.addWidget(self.vat_result)
        vat_button_row.addStretch(1)
        vat_layout.addLayout(vat_button_row)

        vat_box = QGroupBox("Калькулятор НДС")
        vat_box.setLayout(vat_layout)

        # --- Simplified tax (УСН) calculator --------------------------------
        self.income_input = QDoubleSpinBox()
        self.income_input.setRange(0, 1_000_000_000)
        self.income_input.setDecimals(2)
        self.income_input.setValue(100000)

        self.usn_rate_input = QDoubleSpinBox()
        self.usn_rate_input.setRange(0, 100)
        self.usn_rate_input.setDecimals(1)
        self.usn_rate_input.setValue(6.0)
        self.usn_rate_input.setSuffix("%")

        self.usn_button = QPushButton("Рассчитать")
        self.usn_button.clicked.connect(self._calc_usn)

        self.usn_result = QLabel("-")

        usn_form = QFormLayout()
        usn_form.addRow("Доход:", self.income_input)
        usn_form.addRow("Ставка УСН:", self.usn_rate_input)

        usn_layout = QVBoxLayout()
        usn_layout.addLayout(usn_form)
        usn_button_row = QHBoxLayout()
        usn_button_row.addWidget(self.usn_button)
        usn_button_row.addWidget(self.usn_result)
        usn_button_row.addStretch(1)
        usn_layout.addLayout(usn_button_row)

        usn_box = QGroupBox("Налог по УСН «Доходы»")
        usn_box.setLayout(usn_layout)

        # --- Invoice report ---------------------------------------------------
        self.invoices_button = QPushButton("Загрузить отчёт по счетам")
        self.invoices_button.clicked.connect(self._load_invoices)

        self.invoices_export_button = QPushButton("Экспорт в CSV")
        self.invoices_export_button.clicked.connect(self._export_invoices_csv)

        self.invoices_status = QLabel("Нажмите «Загрузить отчёт по счетам»")

        self.invoices_table = QTableWidget()
        self.invoices_table.setColumnCount(len(INVOICE_COLUMNS))
        self.invoices_table.setHorizontalHeaderLabels(INVOICE_COLUMNS)

        invoices_button_row = QHBoxLayout()
        invoices_button_row.addWidget(self.invoices_button)
        invoices_button_row.addWidget(self.invoices_export_button)
        invoices_button_row.addWidget(self.invoices_status)
        invoices_button_row.addStretch(1)

        invoices_layout = QVBoxLayout()
        invoices_layout.addLayout(invoices_button_row)
        invoices_layout.addWidget(self.invoices_table)

        invoices_box = QGroupBox("Отчёт по счетам")
        invoices_box.setLayout(invoices_layout)

        layout = QVBoxLayout()
        layout.addWidget(vat_box)
        layout.addWidget(usn_box)
        layout.addWidget(invoices_box)
        self.setLayout(layout)

        self._runner.finished.connect(self._on_finished)

    def _calc_vat(self) -> None:
        amount = self.amount_input.value()
        rate = VAT_RATES[self.rate_combo.currentIndex()]

        if self.mode_combo.currentIndex() == 0:
            result = vat_from_net(amount, rate)
        else:
            result = vat_from_gross(amount, rate)

        self.vat_result.setText(
            f"Без НДС: {result.net_amount:.2f}  |  НДС: {result.vat_amount:.2f}  |  С НДС: {result.gross_amount:.2f}"
        )

    def _calc_usn(self) -> None:
        income = self.income_input.value()
        rate = self.usn_rate_input.value()
        tax = simplified_tax(income, rate)
        self.usn_result.setText(f"Налог к уплате: {tax:.2f}")

    def _load_invoices(self) -> None:
        self.invoices_button.setEnabled(False)
        self.invoices_status.setText("Загрузка...")
        call_id = self._runner.submit(lambda: mcp_client.list_invoices())
        self._pending[call_id] = "invoices"

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind != "invoices":
            return

        self.invoices_button.setEnabled(True)

        if error is not None:
            self.invoices_status.setText(f"Ошибка загрузки: {error}")
            return

        rows = result or []
        self._populate_invoices(rows)
        self.invoices_status.setText(f"Счетов: {len(rows)}")

    def _populate_invoices(self, rows: list[dict]) -> None:
        self.invoices_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, col in enumerate(INVOICE_COLUMNS):
                value = row.get(col)
                self.invoices_table.setItem(row_idx, col_idx, QTableWidgetItem("" if value is None else str(value)))

    def _export_invoices_csv(self) -> None:
        if self.invoices_table.rowCount() == 0:
            QMessageBox.information(self, "Экспорт в CSV", "Нет данных для экспорта. Сначала загрузите отчёт.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как CSV", "", "CSV files (*.csv)")
        if not path:
            return

        rows = []
        for row_idx in range(self.invoices_table.rowCount()):
            row = []
            for col_idx in range(len(INVOICE_COLUMNS)):
                item = self.invoices_table.item(row_idx, col_idx)
                row.append(item.text() if item is not None else "")
            rows.append(row)

        csv_text = rows_to_csv(INVOICE_COLUMNS, rows)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(csv_text)

        QMessageBox.information(self, "Экспорт в CSV", f"Сохранено: {path}")
