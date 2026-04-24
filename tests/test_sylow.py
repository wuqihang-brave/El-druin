"""Tests for Sylow coset assignment and ultrametric distance.

Verifies:
- SYLOW7_DOMAIN_MAP covers all 7 domain cosets (0–6)
- SYLOW3_MECHANISM_MAP covers all 3 mechanism cosets (0–2)
- get_sylow_coset returns valid (h7, h3) pairs for every registered pattern
- The 3 new social/legal patterns are present in the registry
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from ontology.relation_schema import (
    CARTESIAN_PATTERN_REGISTRY,
    SYLOW7_DOMAIN_MAP,
    SYLOW3_MECHANISM_MAP,
    get_sylow_coset,
)


class TestNewPatterns:
    def test_legal_sovereignty_registered(self):
        names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}
        assert "法律主權 / 司法管轄衝突模式" in names

    def test_social_mobilisation_registered(self):
        names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}
        assert "社會動員 / 民族主義壓力模式" in names

    def test_social_cohesion_registered(self):
        names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}
        assert "社會穩定 / 凝聚力模式" in names

    def test_social_domain_patterns_present(self):
        social_patterns = [
            p for p in CARTESIAN_PATTERN_REGISTRY.values() if p.domain == "social"
        ]
        assert len(social_patterns) == 2

    def test_mutual_inverse_social_patterns(self):
        patterns_by_name = {p.pattern_name: p for p in CARTESIAN_PATTERN_REGISTRY.values()}
        mob = patterns_by_name["社會動員 / 民族主義壓力模式"]
        coh = patterns_by_name["社會穩定 / 凝聚力模式"]
        assert mob.inverse_pattern == "社會穩定 / 凝聚力模式"
        assert coh.inverse_pattern == "社會動員 / 民族主義壓力模式"


class TestSylowCosets:
    def test_all_patterns_have_coset(self):
        for key, pattern in CARTESIAN_PATTERN_REGISTRY.items():
            h7, h3 = get_sylow_coset(pattern.pattern_name)
            assert 0 <= h7 <= 6, f"{pattern.pattern_name}: h7={h7} out of range"
            assert 0 <= h3 <= 2, f"{pattern.pattern_name}: h3={h3} out of range"

    def test_7_distinct_domain_cosets(self):
        domains = {v for v in SYLOW7_DOMAIN_MAP.values()}
        assert len(domains) == 7, f"Expected 7 distinct H₇ coset values, got {domains}"

    def test_3_distinct_mechanism_cosets(self):
        mechs = {v for v in SYLOW3_MECHANISM_MAP.values()}
        assert len(mechs) == 3, f"Expected 3 distinct H₃ coset values, got {mechs}"

    def test_legal_patterns_in_coset_5(self):
        h7, _ = get_sylow_coset("法律主權 / 司法管轄衝突模式")
        assert h7 == 5, f"Legal pattern should be in H₇ coset 5, got {h7}"

    def test_social_patterns_in_coset_6(self):
        h7, _ = get_sylow_coset("社會動員 / 民族主義壓力模式")
        assert h7 == 6, f"Social pattern should be in H₇ coset 6, got {h7}"

    def test_geopolitics_in_coset_0(self):
        h7, _ = get_sylow_coset("霸權制裁模式")
        assert h7 == 0


class TestNewCompositionRules:
    def test_social_mobilisation_hegemonic_sanctions(self):
        from ontology.relation_schema import composition_table
        result = composition_table.get(("社會動員 / 民族主義壓力模式", "霸權制裁模式"))
        assert result == "多邊聯盟制裁模式"

    def test_legal_sovereignty_sanctions(self):
        from ontology.relation_schema import composition_table
        result = composition_table.get(("法律主權 / 司法管轄衝突模式", "霸權制裁模式"))
        assert result == "跨國監管 / 合規約束模式"
