"""
Color Theme — EL-DRUIN Light Blue Rational (Ratio Lucis)
=========================================================

Color constants and utility functions for the 'Light of Reason' aesthetic.

Palette inspired by Palantir Foundry's light mode and Christian 'Ratio Lucis'
(Light of Reason) motifs:
  - Pure white surfaces represent clarity
  - Pale blue background evokes sky / heaven
  - Cobalt blue accents represent truth and order
  - Thin, minimal elements suggest precision
  - Light grey for secondary information (de-emphasised)

WCAG AA/AAA compliance:
  - Cobalt (#0047AB) on white (#FFFFFF): 8.6:1  ✅ AAA
  - Deep grey (#333333) on pale blue (#F0F8FF): 9.2:1 ✅ AAA
  - Mid-grey (#606060) on white (#FFFFFF): 4.9:1 ✅ AA
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Primary palette
# ---------------------------------------------------------------------------
BG_PRIMARY       = "#F0F8FF"   # Alice Blue — main background
BG_SECONDARY     = "#FFFFFF"   # Pure white — cards / containers
BG_SIDEBAR       = "#F5F5F5"   # Light grey — sidebar background

TEXT_PRIMARY     = "#333333"   # Deep grey — body text
TEXT_SECONDARY   = "#606060"   # Mid grey  — labels / captions
TEXT_ACCENT      = "#0047AB"   # Cobalt Blue — headings / accents
TEXT_ACCENT_DARK = "#003580"   # Darker cobalt — hover states

BORDER           = "#E0E0E0"   # Light grey — borders
HALO             = "#F1E5AC"   # Soft champagne — hub node halo

# Graph colours
EDGE_COLOR       = "#A0A0A0"   # Light grey — graph edges
NODE_OUTLINE     = "#0047AB"   # Cobalt Blue — node border (connected)
NODE_SECONDARY   = "#A0A0A0"   # Soft grey — leaf node border
GRAPH_BG         = "#F0F8FF"   # Pale blue — graph canvas background

# ---------------------------------------------------------------------------
# Semantic aliases (for backwards-compatibility with older component code)
# ---------------------------------------------------------------------------
COLOR_ACCENT     = TEXT_ACCENT
COLOR_BG         = BG_PRIMARY
COLOR_TEXT       = TEXT_PRIMARY

# ---------------------------------------------------------------------------
# Ontology-class colour mapping — light rational palette
# ---------------------------------------------------------------------------
ONTOLOGY_LIGHT_COLORS: dict[str, str] = {
    "event":        "#0047AB",   # Cobalt Blue — temporal significance
    "person":       "#2E86AB",   # Cerulean    — agency & consciousness
    "organization": "#1B6CA8",   # Royal Blue  — institutional structures
    "location":     "#2A9D8F",   # Teal        — spatial anchoring
    "concept":      "#606060",   # Mid Grey    — abstract ideas
}
_ONTOLOGY_FALLBACK = "#A0A0A0"


def get_light_node_color(ontology_class: str) -> str:
    """Return the light-theme hex color for a given ontology class.

    Args:
        ontology_class: Raw ontology class string (case-insensitive).

    Returns:
        Hex color string, e.g. ``"#0047AB"``.
    """
    return ONTOLOGY_LIGHT_COLORS.get(ontology_class.lower(), _ONTOLOGY_FALLBACK)


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a ``#RRGGBB`` hex string to an ``rgba(r,g,b,a)`` CSS value.

    Args:
        hex_color: Hex color string (with or without ``#`` prefix).
        alpha: Opacity in the range 0.0–1.0.

    Returns:
        CSS rgba string, e.g. ``"rgba(0,71,171,0.6)"``.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"
