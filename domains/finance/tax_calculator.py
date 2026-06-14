"""Pure helpers for common Russian tax/invoice calculations.

No external dependencies - safe to use from both the MCP server and the
desktop frontend.
"""

from __future__ import annotations

from dataclasses import dataclass

# Common Russian VAT (NDS) rates, percent.
VAT_RATES = (0, 10, 20)


@dataclass(frozen=True)
class VatBreakdown:
    net_amount: float
    vat_rate: float
    vat_amount: float
    gross_amount: float


def vat_from_net(net_amount: float, vat_rate: float) -> VatBreakdown:
    """Compute VAT and gross total from a net (excl. VAT) amount."""
    vat_amount = round(net_amount * vat_rate / 100, 2)
    gross_amount = round(net_amount + vat_amount, 2)
    return VatBreakdown(round(net_amount, 2), vat_rate, vat_amount, gross_amount)


def vat_from_gross(gross_amount: float, vat_rate: float) -> VatBreakdown:
    """Compute the net amount and VAT contained within a gross (incl. VAT) amount."""
    net_amount = round(gross_amount / (1 + vat_rate / 100), 2)
    vat_amount = round(gross_amount - net_amount, 2)
    return VatBreakdown(net_amount, vat_rate, vat_amount, round(gross_amount, 2))


def simplified_tax(income: float, rate: float = 6.0) -> float:
    """Compute simplified taxation system (УСН "доходы") tax for the given income."""
    return round(income * rate / 100, 2)
