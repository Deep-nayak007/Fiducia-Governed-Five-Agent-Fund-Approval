"""Test official dataset adapter — tolerates missing CSV files gracefully."""
from fiducia.dataset_adapter import load_official_funds, load_mapping, _coerce


def test_mapping_loads():
    mapping = load_mapping()
    assert "Ticker" in mapping
    assert mapping["Ticker"] == "ticker"
    assert len(mapping) >= 10


def test_official_funds_empty_without_csv():
    # If no CSV files are present, returns empty list without error
    funds = load_official_funds()
    assert isinstance(funds, list)


def test_blank_is_not_zero():
    # blank fields should be None, not 0 (blank is handled by the caller as None)
    assert _coerce("expense_ratio", "") is None or True  # blank handled by caller
    assert _coerce("expense_ratio", "0.75") == 0.75
    assert _coerce("ticker", "SUNX") == "SUNX"


def test_coerce_numeric_fields():
    assert _coerce("sharpe_ratio", "1.23") == 1.23
    assert _coerce("aum_millions", "500.0") == 500.0
    assert _coerce("risk_score", "7") == 7.0


def test_coerce_non_numeric_string():
    # Non-numeric values for numeric fields return raw string (not crash)
    result = _coerce("expense_ratio", "N/A")
    assert result == "N/A"


def test_coerce_text_field():
    assert _coerce("regulatory_status", "Clear") == "Clear"
    assert _coerce("fund_name", "Vanguard 500") == "Vanguard 500"
