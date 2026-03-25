"""
Three-layer ontological label taxonomies for entity extraction.

Layer 1 – Physical Type  : WHAT the entity IS structurally
Layer 2 – Structural Role: HOW it functions in the narrative
Layer 3 – Virtue / Vice  : Its philosophical / behavioral nature (Bamboo / Plum)
"""

from __future__ import annotations

LAYER1_PHYSICAL_TYPES: dict[str, str] = {
    "PERSON": "Individual human agent",
    "ORGANIZATION": "Institutional entity",
    "COUNTRY": "Geopolitical state",
    "CITY": "Urban center",
    "CORPORATION": "Business entity",
    "REGULATORY_BODY": "Government agency",
    "ALLIANCE": "Coalition/partnership",
    "EVENT": "Temporal occurrence",
    "TECHNOLOGY": "System/tool",
    "IDEOLOGY": "System of beliefs",
    "RESOURCE": "Material asset (oil, minerals, etc.)",
    "CURRENCY": "Monetary system",
    "CONFLICT": "War/dispute",
    "MEDIA": "News source/outlet",
}

LAYER2_STRUCTURAL_ROLES: dict[str, str] = {
    "AGGRESSOR": "Initiates hostile action",
    "DEFENDER": "Responds to aggression",
    "PIVOT": "Kingmaker; swing vote; critical juncture",
    "FRAGILE_STATE": "Vulnerable to collapse",
    "CATALYST": "Triggers major change",
    "REGULATOR": "Controls/restricts others",
    "ENABLER": "Facilitates others' actions",
    "VICTIM": "Suffers consequences",
    "BENEFICIARY": "Gains from situation",
    "OBSERVER": "External commentator",
    "INTERMEDIARY": "Broker/negotiator",
    "VICTIM_TURNED_AGGRESSOR": "Transforms through action",
    "DEUS_EX_MACHINA": "Unexpected intervention",
    "CONSTRAINT": "Limits what's possible",
    "OPPORTUNITY": "Opens new possibilities",
    "HEDGE": "Maintains ambiguous position",
    "AMPLIFIER": "Magnifies existing trends",
}

LAYER3_VIRTUE_VICE: dict[str, str] = {
    # Bamboo – Flexible Virtues
    "RESILIENT": "Bends but doesn't break; adapts and survives",
    "ADAPTIVE": "Changes with circumstance; fluid",
    "PRAGMATIC": "Practical, results-focused; ignores ideology",
    "NEGOTIABLE": "Willing to compromise; seeks consensus",
    "RESPONSIVE": "Reacts to new information; flexible",
    "EMBEDDED": "Connected to networks/community; interdependent",
    # Plum – Unbending Virtues
    "PRINCIPLED": "Won't compromise core values",
    "RIGID": "Inflexible, unchanging; stuck in position",
    "IDEOLOGICAL": "Guided by belief system over pragmatism",
    "DEFIANT": "Resists pressure; oppositional",
    "ISOLATED": "Stands alone; self-sufficient",
    "UNWAVERING": "Steadfast despite pressure; immovable",
    # Deception & Hidden Nature
    "DECEPTIVE": "Hides true intentions",
    "OPAQUE": "Unclear motives/actions; mysterious",
    "DUPLICITOUS": "Acts contradictorily; plays both sides",
    "MASKED": "Presents false face; hides real nature",
    "CALCULATED": "Every move is deliberate; strategic",
    "MANIPULATIVE": "Uses others for own ends",
    # Emergent & Dynamic
    "RISING_POWER": "Growing in strength/influence",
    "DECLINING_POWER": "Losing influence/capacity",
    "TRANSFORMING": "Undergoing fundamental change",
    "CHAOTIC": "Unpredictable behavior; no clear pattern",
    "PARADOXICAL": "Contains internal contradictions",
    "VOLATILE": "Subject to sudden change",
    "STABILIZING": "Dampens volatility; creates equilibrium",
}
