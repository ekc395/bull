"""`tools.supply_chain` — the optional override YAML must never crash analysis.

A missing or malformed `supply_chain.yaml` falls back to `{}` (no overrides);
a valid entry flows through `get_supply_chain_context`. The module memoizes the
parsed YAML and caches per-ticker, so each test resets both globals.
"""

import bull_api.tools.supply_chain as sc


def _reset(monkeypatch, yaml_path):
    monkeypatch.setattr(sc, "_yaml_data", None)
    monkeypatch.setattr(sc, "_cache", {})
    monkeypatch.setattr(sc, "_YAML_PATH", yaml_path)


def test_load_yaml_missing_file_returns_empty(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path / "does_not_exist.yaml")
    assert sc._load_yaml() == {}


def test_load_yaml_malformed_file_returns_empty(monkeypatch, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("NVDA: [unclosed\n  : :\n")
    _reset(monkeypatch, bad)
    assert sc._load_yaml() == {}


def test_load_yaml_valid_file_parses(monkeypatch, tmp_path):
    good = tmp_path / "ok.yaml"
    good.write_text("NVDA:\n  suppliers:\n    - TSMC\n")
    _reset(monkeypatch, good)
    assert sc._load_yaml() == {"NVDA": {"suppliers": ["TSMC"]}}


def test_context_for_known_ticker(monkeypatch, tmp_path):
    good = tmp_path / "ok.yaml"
    good.write_text("NVDA:\n  suppliers:\n    - TSMC\n  customers:\n    - MSFT\n")
    _reset(monkeypatch, good)
    ctx = sc.get_supply_chain_context("nvda")  # case-insensitive key
    assert ctx["suppliers"] == ["TSMC"]
    assert ctx["customers"] == ["MSFT"]
    assert ctx["dependencies"] == []  # missing keys default to []


def test_context_for_unknown_ticker_is_empty_copy(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path / "missing.yaml")
    ctx = sc.get_supply_chain_context("ZZZZ")
    assert ctx == {"suppliers": [], "customers": [], "dependencies": [], "notes": []}
    # A fresh dict, not the shared _EMPTY sentinel.
    assert ctx is not sc._EMPTY
