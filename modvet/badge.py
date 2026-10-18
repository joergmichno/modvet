"""ModVet — deterministischer SVG-Badge-Generator im Shields.io-Stil (stdlib only).

Ausführen: from modvet.badge import badge_svg
"""

# risk_level -> (Statuswort, Farbe)
LEVELS = {
    "CLEAN": ("clean", "#4caf50"),
    "LOW": ("low", "#8bc34a"),
    "MEDIUM": ("warn", "#ffc107"),
    "HIGH": ("high", "#ff9800"),
    "CRITICAL": ("critical", "#f44336"),
}
UNKNOWN = ("unknown", "#9e9e9e")

LABEL = "modvet"
LABEL_COLOR = "#555555"
TEXT_COLOR = "#ffffff"
FONT_SIZE = 11
CHAR_WIDTH = 7  # ~7px pro Zeichen bei Schriftgröße 11
PAD_X = 5  # Innenabstand je Segmentrand
HEIGHT = 20
RADIUS = 3


def _esc(text):
    """Minimales XML-Escaping für Textinhalte."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _seg_width(text):
    return CHAR_WIDTH * len(str(text)) + 2 * PAD_X


def badge_svg(risk_level: str, findings: int, source: str = "mod") -> str:
    """Erzeugt ein 2-Segment-SVG-Badge (Label 'modvet' + Status).

    Deterministisch: gleiche Eingabe -> byte-identische Ausgabe.
    `source` ist für künftige Nutzung reserviert und fließt nicht ins SVG ein.
    """
    key = str(risk_level).strip().upper()
    status_word, status_color = LEVELS.get(key, UNKNOWN)
    status_text = f"{status_word} · {findings}"

    label_w = _seg_width(LABEL)
    status_w = _seg_width(status_text)
    total_w = label_w + status_w
    label_cx = label_w / 2
    status_cx = label_w + status_w / 2
    baseline = HEIGHT - 6  # 14 bei Höhe 20

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" '
        f'height="{HEIGHT}" role="img">\n'
        f"  <title>modvet: {_esc(status_text)}</title>\n"
        f'  <rect width="{total_w}" height="{HEIGHT}" rx="{RADIUS}" '
        f'fill="{LABEL_COLOR}"/>\n'
        f'  <rect x="{label_w}" width="{status_w}" height="{HEIGHT}" '
        f'rx="{RADIUS}" fill="{status_color}"/>\n'
        f'  <rect x="{label_w}" width="{RADIUS}" height="{HEIGHT}" '
        f'fill="{status_color}"/>\n'
        f'  <g fill="{TEXT_COLOR}" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="{FONT_SIZE}">\n'
        f'    <text x="{label_cx}" y="{baseline}">{LABEL}</text>\n'
        f'    <text x="{status_cx}" y="{baseline}">{_esc(status_text)}</text>\n'
        f"  </g>\n"
        "</svg>\n"
    )
