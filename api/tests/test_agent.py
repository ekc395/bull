"""`agent._coerce_report` — defensive normalization of the model's `report`.

Opus sometimes returns the report with non-string field values, or as one
string carrying the internal `<parameter name="...">` XML instead of a JSON
object. `_coerce_report` must stringify (not drop) values, parse the XML
fallback, and pad the five report fields so the response schema stays valid.
"""

from bull_api.agent import _REPORT_FIELDS, _coerce_report


def test_coerce_report_stringifies_non_string_values():
    report = {
        "technical": 42,
        "fundamentals_and_supply_chain": "fine",
        "news_sentiment": "ok",
        "risks": ["x", "y"],
        "reasoning": 3.5,
    }
    assert _coerce_report(report) == {
        "technical": "42",
        "fundamentals_and_supply_chain": "fine",
        "news_sentiment": "ok",
        "risks": "['x', 'y']",
        "reasoning": "3.5",
    }


def test_coerce_report_pads_missing_fields():
    out = _coerce_report({"technical": "t"})
    assert set(out) == set(_REPORT_FIELDS)
    assert out["technical"] == "t"
    assert out["risks"] == ""
    assert out["reasoning"] == ""


def test_coerce_report_parses_parameter_xml_string():
    xml = (
        '<parameter name="technical">RSI is low</parameter>'
        '<parameter name="risks">earnings soon</parameter>'
    )
    out = _coerce_report(xml)
    assert out["technical"] == "RSI is low"
    assert out["risks"] == "earnings soon"
    assert out["reasoning"] == ""  # padded


def test_coerce_report_parses_unclosed_parameter_tags():
    # Opus sometimes omits the closing </parameter>; the regex still splits.
    xml = '<parameter name="technical">a<parameter name="risks">b'
    out = _coerce_report(xml)
    assert out["technical"] == "a"
    assert out["risks"] == "b"


def test_coerce_report_plain_string_becomes_reasoning():
    out = _coerce_report("Just a blob of analysis.")
    assert out["reasoning"] == "Just a blob of analysis."
    assert out["technical"] == ""


def test_coerce_report_non_dict_non_str_yields_all_empty():
    assert _coerce_report(None) == {k: "" for k in _REPORT_FIELDS}
