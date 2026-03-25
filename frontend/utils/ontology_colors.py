"""
Ontology Color Mapping – EL-DRUIN Intelligence Platform
========================================================

Maps ontological classes to colors and philosophical meanings.

The color palette encodes philosophical significance:
  - Each color reflects the *essence* of the ontological class
  - Colors are drawn from precious metals / gems to reflect the
    Divine Geometry aesthetic of the platform.

Usage::

    from utils.ontology_colors import get_node_color, get_ontology_meaning

    color = get_node_color("Event")      # → "#0047AB"
    meaning = get_ontology_meaning("Person")  # → "Agency & consciousness..."
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Ontology class → hex color
# ---------------------------------------------------------------------------

#: Canonical color palette for the five primary ontological classes.
#: Key: lowercase ontology class name (also matched case-insensitively).
#: Precious-metals palette — Gold, Silver, Bronze for primary classes.
ONTOLOGY_COLORS: Dict[str, str] = {
    "event":        "#D4AF37",  # Gold — temporal significance
    "person":       "#A8A8A8",  # Silver — agency & consciousness
    "organization": "#CD7F32",  # Bronze — institutional structures
    "location":     "#2A9D8F",  # Teal — spatial anchoring
    "concept":      "#606060",  # Mid Grey — abstract ideas
}

#: Fallback color for unknown / unmapped ontological classes.
_DEFAULT_COLOR = "#A0A0A0"

# ---------------------------------------------------------------------------
# Ontology class → philosophical meaning
# ---------------------------------------------------------------------------

ONTOLOGY_MEANINGS: Dict[str, str] = {
    "event":        "Temporal significance — moments that change the world",
    "person":       "Agency & consciousness — intentional actors",
    "organization": "Institutional structures — collective entities",
    "location":     "Spatial anchoring — places in the world",
    "concept":      "Abstract ideas — eternal truths",
}

_DEFAULT_MEANING = "Undefined essence — awaiting ontological classification"

# ---------------------------------------------------------------------------
# Legacy / NLP type aliases → canonical ontology class
# (so that NLP-generated types like PERSON, ORG, GPE still resolve correctly)
# ---------------------------------------------------------------------------

_TYPE_ALIASES: Dict[str, str] = {
    # People
    "person":  "person",
    "per":     "person",
    "people":  "person",
    # Organisations
    "organization":  "organization",
    "organisation":  "organization",
    "org":           "organization",
    "company":       "organization",
    "institution":   "organization",
    # Locations
    "location": "location",
    "loc":      "location",
    "gpe":      "location",
    "facility": "location",
    "place":    "location",
    # Events
    "event": "event",
    "ev":    "event",
    # Concepts
    "concept":    "concept",
    "misc":       "concept",
    "date":       "concept",
    "time":       "concept",
    "money":      "concept",
    "percent":    "concept",
    "quantity":   "concept",
    "ordinal":    "concept",
    "cardinal":   "concept",
    "law":        "concept",
    "language":   "concept",
    "product":    "concept",
    "work_of_art":"concept",
}


def _canonicalize(ontology_class: str) -> str:
    """Return the canonical lowercase ontology class, resolving aliases."""
    key = ontology_class.lower().strip()
    return _TYPE_ALIASES.get(key, key)


def get_node_color(ontology_class: str) -> str:
    """Return the hex color associated with *ontology_class*.

    Falls back to :data:`_DEFAULT_COLOR` for unknown classes.

    Args:
        ontology_class: An ontological class name, e.g. ``"Event"`` or
            ``"ORG"`` (case-insensitive; NLP-style aliases are resolved).

    Returns:
        Hex color string such as ``"#0047AB"``.
    """
    canonical = _canonicalize(ontology_class)
    return ONTOLOGY_COLORS.get(canonical, _DEFAULT_COLOR)


def get_ontology_meaning(ontology_class: str) -> str:
    """Return the philosophical meaning associated with *ontology_class*.

    Falls back to :data:`_DEFAULT_MEANING` for unknown classes.

    Args:
        ontology_class: An ontological class name (case-insensitive).

    Returns:
        A short philosophical description string.
    """
    canonical = _canonicalize(ontology_class)
    return ONTOLOGY_MEANINGS.get(canonical, _DEFAULT_MEANING)


def get_canonical_class(ontology_class: str) -> str:
    """Return the canonical display name (title-case) for *ontology_class*.

    Args:
        ontology_class: Raw class name from entity data.

    Returns:
        Title-case canonical class name, e.g. ``"Event"``.
    """
    canonical = _canonicalize(ontology_class)
    if canonical in ONTOLOGY_COLORS:
        return canonical.title()
    return ontology_class.title()


#: Ordered list of canonical ontology class names for UI display.
ALL_ONTOLOGY_CLASSES = ["Event", "Person", "Organization", "Location", "Concept"]
