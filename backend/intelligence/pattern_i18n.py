"""Pattern name internationalisation (localisation) for El-druin.

Internal ontology keys use CJK (Chinese) identifiers so that
composition_table / inverse_table lookups remain stable.

This module provides a mapping layer that converts those internal keys to
English display strings for all user-visible and API outputs.  Nothing in
this file should break internal computations — the raw CJK keys are
preserved throughout the reasoning pipeline and only converted at the final
serialisation boundary.

Usage
-----
    from intelligence.pattern_i18n import display_pattern, has_cjk

    en_label = display_pattern("霸權制裁模式")  # → "Hegemonic Sanctions"
    clean    = not has_cjk(en_label)            # → True
"""

from __future__ import annotations

import re
from typing import Dict

# ---------------------------------------------------------------------------
# Central mapping: internal CJK key → English display label
# ---------------------------------------------------------------------------
# Every pattern registered in CARTESIAN_PATTERN_REGISTRY (relation_schema.py)
# appears here.  Derived/composite patterns from composition_table are
# included as well.  Keeping this mapping in a single authoritative place
# ensures a consistent English surface across active_patterns, derived_patterns,
# top_transitions, probability_tree nodes/edges, and alpha/beta path names.
# ---------------------------------------------------------------------------

PATTERN_DISPLAY_EN: Dict[str, str] = {
    # ── Geopolitical / coercive ──────────────────────────────────────────
    "霸權制裁模式":                       "Hegemonic Sanctions",
    "實體清單技術封鎖模式":                "Entity-List Technology Blockade",
    "國家間武力衝突模式":                  "Interstate Military Conflict",
    "大國脅迫 / 威懾模式":                "Great-Power Coercion / Deterrence",
    "多邊聯盟制裁模式":                    "Multilateral Alliance Sanctions",
    "非國家武裝代理衝突模式":              "Non-State Armed Proxy Conflict",
    "正式軍事同盟模式":                    "Formal Military Alliance",
    "國際規範建構模式":                    "International Norm Construction",
    "信息戰 / 敘事操控模式":              "Information Warfare / Narrative Control",
    # ── Trade / economic ────────────────────────────────────────────────
    "雙邊貿易依存模式":                    "Bilateral Trade Dependency",
    "央行貨幣政策傳導模式":                "Central Bank Monetary Transmission",
    "金融孤立 / SWIFT 切斷模式":         "Financial Isolation / SWIFT Cut-Off",
    "企業供應鏈單點依賴模式":              "Single-Point Supply Chain Dependency",
    "資源依賴 / 能源武器化模式":           "Resource Dependency / Energy Weaponisation",
    "貿易戰 / 脫鉤模式":                  "Trade War / Decoupling",
    "跨國監管 / 合規約束模式":             "Cross-Border Regulatory / Compliance Constraint",
    "政策性貿易限制模式":                  "Policy-Driven Trade Restriction",
    # ── Technology / supply chain ────────────────────────────────────────
    "技術標準主導模式":                    "Technology Standards Leadership",
    "關鍵零部件寡頭供應模式":              "Critical Components Oligopoly Supply",
    "科技脫鉤 / 技術鐵幕模式":            "Tech Decoupling / Technology Iron Curtain",
    "技術突破 / 太空探索模式":             "Technology Breakthrough / Space Exploration",
    # ── De-escalation / inverse patterns ────────────────────────────────
    "制裁解除 / 正常化模式":              "Sanctions Relief / Normalisation",
    "技術許可 / 解禁模式":                "Technology Licence / Unblocking",
    "停火 / 和平協議模式":                "Ceasefire / Peace Agreement",
    "外交讓步 / 去升級模式":              "Diplomatic Concession / De-escalation",
    "多邊制裁解除模式":                    "Multilateral Sanctions Relief",
    "代理武裝解除模式":                    "Proxy Disarmament",
    "寬鬆週期模式":                        "Monetary Easing Cycle",
    "金融再整合模式":                      "Financial Reintegration",
    "供應鏈多元化模式":                    "Supply Chain Diversification",
    "能源多元化 / 去依賴模式":             "Energy Diversification / Dependency Reduction",
    "標準競爭失敗 / 替代標準崛起模式":    "Standard Competition Failure / Alternative Standard Rise",
    "供應市場競爭充分化模式":              "Supply Market Competitive Saturation",
    "技術合作再融合模式":                  "Technology Cooperation Reintegration",
    "信息環境修復模式":                    "Information Environment Restoration",
    "監管放鬆 / 去規制模式":              "Regulatory Easing / De-regulation",
    "同盟瓦解 / 中立化模式":              "Alliance Dissolution / Neutralisation",
    "規範侵蝕 / 去合法化模式":            "Norm Erosion / De-legitimisation",
    # ── Business / platform ──────────────────────────────────────────────
    "產品能力擴張模式":                    "Product Capability Expansion",
    "平台競爭 / 生態位擴張模式":           "Platform Competition / Niche Expansion",
    "創作者經濟整合模式":                  "Creator Economy Integration",
    "產品能力收縮模式":                    "Product Capability Contraction",
    "市場壟斷 / 競爭消解模式":             "Market Monopoly / Competition Dissolution",
    "創作者平台分散模式":                  "Creator Platform Fragmentation",
    "技術瓶頸 / 任務失敗模式":             "Technology Bottleneck / Mission Failure",
}

# ---------------------------------------------------------------------------
# CJK Unicode block detector
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(
    r"[\u4e00-\u9fff"    # CJK Unified Ideographs
    r"\u3400-\u4dbf"     # CJK Extension A
    r"\uf900-\ufaff"     # CJK Compatibility Ideographs
    r"\u3000-\u303f"     # CJK Symbols and Punctuation
    r"\uff00-\uffef]"    # Halfwidth / Fullwidth Forms
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def display_pattern(name: str) -> str:
    """Return the English display label for an internal ontology pattern key.

    If *name* is already in the mapping, the English label is returned.
    If *name* is not found (e.g. already English, a synthetic fallback like
    "Status Quo Continuation", or ``"(inverse)"``), the name is returned
    unchanged after stripping any residual CJK characters as a safety net.

    This function must **never** be called on names that feed back into
    composition_table / inverse_table lookups — use the raw internal key there.
    """
    mapped = PATTERN_DISPLAY_EN.get(name)
    if mapped is not None:
        return mapped
    # Fallback: strip any residual CJK to guarantee no leakage into outputs
    cleaned = _CJK_RE.sub("", name).strip(" /\u3000")
    # If stripping left nothing (entire string was CJK), return a safe placeholder
    return cleaned if cleaned else "(unrecognized pattern)"


def has_cjk(text: str) -> bool:
    """Return ``True`` if *text* contains any CJK characters."""
    return bool(_CJK_RE.search(text))


def strip_cjk(text: str) -> str:
    """Remove all CJK characters from *text* and return the cleaned string."""
    return _CJK_RE.sub("", text).strip()
