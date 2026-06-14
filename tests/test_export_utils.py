from frontend.export_utils import rows_to_csv


def test_rows_to_csv_basic():
    csv_text = rows_to_csv(["name", "amount"], [["Acme", "100"], ["Beta", "200"]])

    assert csv_text == "name,amount\r\nAcme,100\r\nBeta,200\r\n"


def test_rows_to_csv_empty_rows():
    csv_text = rows_to_csv(["name", "amount"], [])

    assert csv_text == "name,amount\r\n"


def test_rows_to_csv_escapes_commas_and_quotes():
    csv_text = rows_to_csv(["name"], [['Acme, "Inc"']])

    assert csv_text == 'name\r\n"Acme, ""Inc"""\r\n'
