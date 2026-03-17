from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO_ROOT / "frontend" / "src" / "index.html"
STYLE_CSS = REPO_ROOT / "frontend" / "src" / "style.css"


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
