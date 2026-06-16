"""Headless QApplication tests for FinanceTab.

These tests require PyQt6 (installed as an optional dependency).
They are automatically skipped when PyQt6 is not available (e.g. on CI
without GUI libraries).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 not installed — skipping GUI tests")

# Allow importing frontend modules without a display.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))


@pytest.fixture()
def tab(qt_app):
    from async_runner import AsyncRunner
    from pages.finance_tab import FinanceTab

    runner = AsyncRunner()
    widget = FinanceTab(runner)
    yield widget
    runner.shutdown()


# ---------------------------------------------------------------------------
# VAT calculator
# ---------------------------------------------------------------------------

def test_calc_vat_from_net_updates_label(tab):
    tab.amount_input.setValue(1000)
    tab.rate_combo.setCurrentIndex(2)  # 20%
    tab.mode_combo.setCurrentIndex(0)  # net

    tab._calc_vat()

    text = tab.vat_result.text()
    assert "1000.00" in text
    assert "200.00" in text
    assert "1200.00" in text


def test_calc_vat_from_gross_updates_label(tab):
    tab.amount_input.setValue(1200)
    tab.rate_combo.setCurrentIndex(2)  # 20%
    tab.mode_combo.setCurrentIndex(1)  # gross (incl. VAT)

    tab._calc_vat()

    text = tab.vat_result.text()
    assert "1000.00" in text
    assert "200.00" in text
    assert "1200.00" in text


def test_calc_vat_zero_rate(tab):
    tab.amount_input.setValue(500)
    tab.rate_combo.setCurrentIndex(0)  # 0%
    tab.mode_combo.setCurrentIndex(0)

    tab._calc_vat()

    text = tab.vat_result.text()
    assert "500.00" in text
    assert "0.00" in text


# ---------------------------------------------------------------------------
# USN calculator
# ---------------------------------------------------------------------------

def test_calc_usn_default_rate(tab):
    tab.income_input.setValue(100_000)
    tab.usn_rate_input.setValue(6.0)

    tab._calc_usn()

    assert "6000.00" in tab.usn_result.text()


def test_calc_usn_custom_rate(tab):
    tab.income_input.setValue(200_000)
    tab.usn_rate_input.setValue(15.0)

    tab._calc_usn()

    assert "30000.00" in tab.usn_result.text()


# ---------------------------------------------------------------------------
# Invoice report table
# ---------------------------------------------------------------------------

_SAMPLE_INVOICES = [
    {
        "number": "INV-001",
        "amount": 120000.0,
        "currency": "RUB",
        "vat_rate": 20,
        "due_date": "2026-07-01",
        "issuer": "ООО Альфа",
        "payer": "ООО Бета",
    },
    {
        "number": "INV-002",
        "amount": 55000.0,
        "currency": "RUB",
        "vat_rate": 10,
        "due_date": "2026-08-15",
        "issuer": "ООО Альфа",
        "payer": "ООО Гамма",
    },
]


def test_populate_invoices_fills_rows(tab):
    tab._populate_invoices(_SAMPLE_INVOICES)

    assert tab.invoices_table.rowCount() == 2
    assert tab.invoices_table.columnCount() == 7


def test_populate_invoices_correct_values(tab):
    tab._populate_invoices(_SAMPLE_INVOICES)

    # First row: number
    assert tab.invoices_table.item(0, 0).text() == "INV-001"
    # First row: amount
    assert tab.invoices_table.item(0, 1).text() == "120000.0"
    # First row: issuer
    assert tab.invoices_table.item(0, 5).text() == "ООО Альфа"
    # Second row: payer
    assert tab.invoices_table.item(1, 6).text() == "ООО Гамма"


def test_populate_invoices_empty_clears_table(tab):
    tab._populate_invoices(_SAMPLE_INVOICES)
    tab._populate_invoices([])

    assert tab.invoices_table.rowCount() == 0


def test_populate_invoices_handles_none_values(tab):
    tab._populate_invoices([{"number": "X", "amount": None, "currency": None,
                              "vat_rate": None, "due_date": None, "issuer": None, "payer": None}])

    # None values must render as empty strings, not crash.
    assert tab.invoices_table.item(0, 0).text() == "X"
    assert tab.invoices_table.item(0, 1).text() == ""


# ---------------------------------------------------------------------------
# Runner integration: on_finished routing
# ---------------------------------------------------------------------------

def test_on_finished_wrong_kind_ignored(tab):
    """Results for unknown call IDs must not affect the table."""
    tab._populate_invoices(_SAMPLE_INVOICES)

    tab._on_finished("unknown-id", [], None)

    assert tab.invoices_table.rowCount() == 2  # unchanged


def test_on_finished_error_updates_status(tab):
    tab._pending["err-call"] = "invoices"

    tab._on_finished("err-call", None, RuntimeError("connection refused"))

    assert "connection refused" in tab.invoices_status.text()
    assert tab.invoices_button.isEnabled()


def test_on_finished_success_populates_table(tab):
    tab._pending["ok-call"] = "invoices"

    tab._on_finished("ok-call", _SAMPLE_INVOICES, None)

    assert tab.invoices_table.rowCount() == 2
    assert "2" in tab.invoices_status.text()
