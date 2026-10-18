"""Tests für modvet/badge.py — SVG-Badge-Generator (stdlib only).

Ausführen: python tests/test_badge.py
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modvet.badge import badge_svg  # noqa: E402


def test_clean_green():
    svg = badge_svg("CLEAN", 0)
    assert "clean" in svg, svg
    assert "#4caf50" in svg, svg
    assert "warn" not in svg, svg
    assert "critical" not in svg, svg
    print("PASS CLEAN -> clean/grün, ohne warn/critical")


def test_critical_red():
    svg = badge_svg("CRITICAL", 12)
    assert "critical" in svg, svg
    assert "#f44336" in svg, svg
    assert "12" in svg, svg
    print("PASS CRITICAL -> critical/rot")


def test_low_warn_equivalence():
    low = badge_svg("LOW", 1)
    assert "low" in low and "#8bc34a" in low, low
    med = badge_svg("MEDIUM", 3)
    assert "warn" in med and "#ffc107" in med, med
    print("PASS LOW -> low/hellgrün, MEDIUM -> warn/gelb")


def test_unknown_gray():
    svg = badge_svg("KOMPLETT_FREMD", 7)
    assert "unknown" in svg, svg
    assert "#9e9e9e" in svg, svg
    print("PASS unbekanntes Level -> unknown/grau")


def test_valid_xml():
    cases = [("CLEAN", 0), ("LOW", 1), ("MEDIUM", 2), ("HIGH", 3), ("CRITICAL", 9), ("???", 4)]
    for level, findings in cases:
        svg = badge_svg(level, findings)
        root = ET.fromstring(svg)  # wirft ParseError bei ungültigem XML
        assert root.tag == "{http://www.w3.org/2000/svg}svg", root.tag
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg, "xmlns fehlt"
    # deterministisch: gleiche Eingabe -> identische Ausgabe
    assert badge_svg("MEDIUM", 2) == badge_svg("MEDIUM", 2)
    print("PASS gültiges, deterministisches XML/SVG für alle Level")


if __name__ == "__main__":
    tests = [
        test_clean_green,
        test_critical_red,
        test_low_warn_equivalence,
        test_unknown_gray,
        test_valid_xml,
    ]
    for t in tests:
        t()
    print(f"\nALL {len(tests)} TESTS PASSED")
