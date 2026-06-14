from domains.finance.tax_calculator import VatBreakdown, simplified_tax, vat_from_gross, vat_from_net


def test_vat_from_net_standard_rate():
    result = vat_from_net(1000, 20)

    assert result == VatBreakdown(1000.0, 20, 200.0, 1200.0)


def test_vat_from_net_zero_rate():
    result = vat_from_net(1000, 0)

    assert result == VatBreakdown(1000.0, 0, 0.0, 1000.0)


def test_vat_from_gross_standard_rate():
    result = vat_from_gross(1200, 20)

    assert result == VatBreakdown(1000.0, 20, 200.0, 1200.0)


def test_vat_from_gross_rounds_correctly():
    result = vat_from_gross(100, 20)

    assert result.net_amount == 83.33
    assert result.vat_amount == 16.67


def test_simplified_tax_default_rate():
    assert simplified_tax(100_000) == 6000.0


def test_simplified_tax_custom_rate():
    assert simplified_tax(100_000, rate=15) == 15000.0
