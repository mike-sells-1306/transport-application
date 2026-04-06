from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "frontend" / "src" / "index.html"
STYLE_CSS = REPO_ROOT / "frontend" / "src" / "style.css"
MAIN_JS = REPO_ROOT / "frontend" / "src" / "main.js"


def test_accessibility_menu_uses_common_colour_blind_names():
    html = INDEX_HTML.read_text(encoding="utf-8")

    expected_labels = [
        "Red–Green (Deuteranopia)",
        "Red–Green (Protanopia)",
        "Blue–Yellow (Tritanopia)",
        "Monochrome (Achromatopsia)",
    ]

    for label in expected_labels:
        assert label in html


def test_accessibility_modes_include_sidebar_theming_rules():
    css = STYLE_CSS.read_text(encoding="utf-8")

    # Ensure mode classes exist so sidebar palette variables change by mode
    for selector in [
        "body.accessibility-mode-deuteranopia {",
        "body.accessibility-mode-protanopia {",
        "body.accessibility-mode-tritanopia {",
        "body.accessibility-mode-achromatopsia {",
    ]:
        assert selector in css

    # Ensure explicit sidebar link styling is present for each non-default mode
    for selector in [
        "body.colorblind-mode .sidebar-links",
        "body.accessibility-mode-protanopia .sidebar-links",
        "body.accessibility-mode-tritanopia .sidebar-links",
        "body.accessibility-mode-achromatopsia .sidebar-links",
    ]:
        assert selector in css


def test_map_markers_use_accessibility_first_palette_contract():
    js = MAIN_JS.read_text(encoding="utf-8")

    # Accessibility modes should use a stable palette independent of basemap style.
    for token in [
        "const accessibleModePalette = {",
        "deuteranopia:",
        "protanopia:",
        "tritanopia:",
        "achromatopsia:",
    ]:
        assert token in js

    # Default mode remains style-aware so marker contrast can adapt by map style.
    assert "const defaultStylePalette = {" in js


def test_map_style_changes_trigger_marker_restyle():
    js = MAIN_JS.read_text(encoding="utf-8")
    assert "activeMapStyleId = selected.id;" in js
    assert "updateMapMarkerColors();" in js


def test_accessibility_modes_define_default_map_styles():
    js = MAIN_JS.read_text(encoding="utf-8")

    assert "const ACCESSIBILITY_MODE_DEFAULT_MAP_STYLE = {" in js
    for mode in ["deuteranopia", "protanopia", "tritanopia", "achromatopsia"]:
        assert f"{mode}:" in js

    # Ensure the defaults are applied when mode changes.
    assert "window.appMap.setMapStyleById" in js
    assert "normalized.colorMode !== previousColorMode" in js


def test_map_style_button_ui_updates_after_programmatic_style_change():
    js = MAIN_JS.read_text(encoding="utf-8")
    assert "function updateMapStyleButtonUI(style)" in js
    assert "map.setMapStyleById = function(styleId)" in js
