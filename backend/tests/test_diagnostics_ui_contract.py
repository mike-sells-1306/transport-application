from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "frontend" / "src" / "index.html"
MAIN_JS = REPO_ROOT / "frontend" / "src" / "main.js"
LOCALE_EN_GB = REPO_ROOT / "frontend" / "src" / "locales" / "en-GB.json"


def test_diagnostics_navigation_and_panel_contract_present():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="diagnostics-link"' in html
    assert 'id="diagnostics-panel"' in html
    assert 'id="diagnostics-refresh-btn"' in html


def test_panel_orchestration_and_diagnostics_handlers_present():
    js = MAIN_JS.read_text(encoding="utf-8")
    assert "function closeOverlaySurfaces" in js
    assert "function attachDiagnosticsEventHandlers" in js
    assert "function refreshDiagnosticsPanel" in js
    assert "closeOverlaySurfaces({ except: ['diagnostics'] })" in js


def test_diagnostics_localization_keys_exist():
    content = LOCALE_EN_GB.read_text(encoding="utf-8")
    assert '"diagnostics": {' in content
    assert '"diagnosticsLoaded"' in content
    assert '"diagnosticsLoadFailed"' in content
