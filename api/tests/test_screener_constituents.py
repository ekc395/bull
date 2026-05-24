"""Wikipedia parser + symbol normalization."""

import pytest

from bull_api.screener.constituents import normalize_symbol, parse_constituents_html


def test_normalize_symbol_dot_to_dash():
    assert normalize_symbol("BRK.B") == "BRK-B"
    assert normalize_symbol("BF.B") == "BF-B"


def test_normalize_symbol_uppercases_and_strips():
    assert normalize_symbol("  aapl  ") == "AAPL"


def test_normalize_symbol_passthrough():
    assert normalize_symbol("NVDA") == "NVDA"


def _row(symbol: str, name: str, sector: str) -> str:
    return (
        f"<tr><td>{symbol}</td><td>{name}</td><td>{sector}</td>"
        f"<td>Sub-Industry</td></tr>"
    )


def _table(rows: list[str]) -> str:
    return (
        "<html><body>"
        '<table id="constituents"><tbody>'
        "<tr><th>Symbol</th><th>Security</th><th>Sector</th><th>Sub</th></tr>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )


def test_parse_extracts_rows_and_normalizes():
    rows = [_row(f"TKR{i}", f"Co {i}", "Information Technology") for i in range(400)]
    rows.insert(0, _row("BRK.B", "Berkshire Hathaway", "Financials"))
    rows.insert(1, _row("AAPL", "Apple Inc.", "Information Technology"))
    out = parse_constituents_html(_table(rows))

    assert out[0].symbol == "BRK-B"
    assert out[0].company_name == "Berkshire Hathaway"
    assert out[0].sector == "Financials"
    assert out[1].symbol == "AAPL"
    assert len(out) == 402


def test_parse_missing_table_raises():
    with pytest.raises(ValueError, match="constituents table not found"):
        parse_constituents_html("<html><body>no table here</body></html>")


def test_parse_too_few_rows_raises():
    rows = [_row(f"TKR{i}", f"Co {i}", "Tech") for i in range(50)]
    with pytest.raises(ValueError, match="parsed 50"):
        parse_constituents_html(_table(rows))


def test_parse_skips_malformed_rows():
    rows = [_row(f"TKR{i}", f"Co {i}", "Tech") for i in range(400)]
    rows.append("<tr><td>JUSTONECELL</td></tr>")
    rows.append(_row("", "", ""))
    out = parse_constituents_html(_table(rows))
    assert len(out) == 400
