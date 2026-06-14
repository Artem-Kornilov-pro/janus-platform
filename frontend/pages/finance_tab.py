from __future__ import annotations

import sys
from pathlib import Path

if (project_root := str(Path(__file__).resolve().parents[2])) not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domains.finance.tax_calculator import VAT_RATES, simplified_tax, vat_from_gross, vat_from_net


class FinanceTab(QWidget):
    """Quick calculators for everyday finance/accounting tasks."""

    def __init__(self) -> None:
        super().__init__()

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

        layout = QVBoxLayout()
        layout.addWidget(vat_box)
        layout.addWidget(usn_box)
        layout.addStretch(1)
        self.setLayout(layout)

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
