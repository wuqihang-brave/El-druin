"""
Sacred Sword Analyzer – EL-DRUIN Intelligence Platform
=======================================================

Ontological reasoning engine performing rigorous 4-step analysis:

1. Fact Anchoring       – extract 3-5 core facts from news fragments
2. Conflict Detection   – binary [CONSISTENT] / [CONFLICT] check
3. Causal Branching     – Alpha (high-confidence) and Beta (black-swan) paths
4. Self-Audit           – confidence score, critical data gap, counter-argument

Anti-Over-Cook Protocol: no complex matrices, no 10,000 variables.
Fixed probabilities: Alpha=0.72, Beta=0.28.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class ConflictStatus(Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"


@dataclass
class Fact:
    statement: str      # Single clear statement
    source: str         # One source line
    confidence: float   # 0.0-1.0


@dataclass
class Branch:
    name: str               # "Alpha" or "Beta"
    description: str        # One sentence evolution
    probability: float      # 0.72 or 0.28
    key_assumption: str     # Core assumption in one sentence


@dataclass
class SacredSwordAnalysis:
    facts: List[Fact]           # 3-5 facts max
    conflict: ConflictStatus    # Binary decision
    alpha: Branch               # High confidence path
    beta: Branch                # Black swan scenario
    confidence_score: float     # 0.0-1.0 single number
    data_gap: str               # ONE critical gap
    counter_arg: str            # Strongest opposing view (100 words max)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

_KNOWN_ENTITY_CONFIDENCE = 0.95
_UNKNOWN_ENTITY_CONFIDENCE = 0.75  # Below threshold, rejected
_CONFIDENCE_THRESHOLD = 0.85
_MAX_FACTS = 5
_ALPHA_PROBABILITY = 0.72
_BETA_PROBABILITY = 0.28
_CONFLICT_PENALTY = 0.2


class SacredSwordAnalyzer:
    """Sacred Sword Analyzer – 4-step ontological reasoning engine."""

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._client_type = None
        self._client = None
        if self._settings is not None:
          self._client_type = getattr(self._settings, "llm_provider", None)
        if self._client_type == "groq":
            import groq
            self._client = groq.Groq(
                api_key=self._settings.groq_api_key,
                # ...其他client参数
            )
        elif self._client_type == "openai":
            import openai
            self._client = openai.OpenAI(
                api_key=self._settings.openai_api_key,
            )
    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(
        self,
        news_fragments: List[str],
        graph_context: Dict[str, Any],
        claim: str,
    ) -> SacredSwordAnalysis:
        """Execute the full 4-step Sacred Sword analysis protocol."""
        # Step 1: Fact anchoring
        facts = self._extract_core_facts(news_fragments, graph_context)

        # Step 2: Conflict detection
        conflict = self._detect_conflict(facts)

        # Step 3: Causal branching
        alpha = self._generate_alpha_branch(facts, claim)
        beta = self._generate_beta_branch(facts, claim, alpha)

        # Step 4: Self-audit
        confidence_score = self._calculate_confidence(facts, conflict)
        data_gap = self._identify_one_critical_gap(facts, claim)
        counter_arg = self._find_strongest_counter_arg(facts, claim)

        return SacredSwordAnalysis(
            facts=facts,
            conflict=conflict,
            alpha=alpha,
            beta=beta,
            confidence_score=confidence_score,
            data_gap=data_gap,
            counter_arg=counter_arg,
        )

    # ------------------------------------------------------------------
    # Step 1: Fact anchoring
    # ------------------------------------------------------------------

    def _extract_core_facts(
        self,
        news: List[str],
        graph: Dict[str, Any],
    ) -> List[Fact]:
        """Parse news fragments, anchor facts against the knowledge graph.

        Simple rule:
          - Entity found in graph → confidence 0.95 (accepted)
          - Entity not in graph   → confidence 0.75 (below threshold, rejected)
        Returns at most 5 facts.
        """
        known_entities: set[str] = set()
        for key in ("entities", "nodes"):
            raw = graph.get(key, [])
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("id") or ""
                    else:
                        name = str(item)
                    if name:
                        known_entities.add(name.lower())

        facts: List[Fact] = []
        for fragment in news:
            if len(facts) >= _MAX_FACTS:
                break
            fragment = fragment.strip()
            if not fragment:
                continue
            # Determine source label: use first sentence up to 60 chars
            source = fragment[:60].rstrip(" .") + ("…" if len(fragment) > 60 else "")

            # Check whether any known entity appears in this fragment
            fragment_lower = fragment.lower()
            entity_found = any(ent in fragment_lower for ent in known_entities)

            conf = _KNOWN_ENTITY_CONFIDENCE if entity_found else _UNKNOWN_ENTITY_CONFIDENCE
            if conf < _CONFIDENCE_THRESHOLD:
                logger.debug("Fragment rejected (confidence %.2f < threshold): %s", conf, fragment[:60])
                continue

            facts.append(Fact(statement=fragment, source=source, confidence=conf))

        # If LLM is available, refine with LLM extraction and enrich with
        # three-layer entity context (Layer 1 / 2 / 3 ontological labels).
        if self._settings is not None and getattr(self._settings, "llm_enabled", False):
            facts = self._llm_refine_facts(facts, news, graph)
            facts = self._enrich_facts_with_entity_labels(facts, news)

        return facts[:_MAX_FACTS]

    # ------------------------------------------------------------------
    # Step 2: Conflict detection
    # ------------------------------------------------------------------

    def _detect_conflict(self, facts: List[Fact]) -> ConflictStatus:
        """Binary conflict detection via LLM, falling back to CONSISTENT."""
        if not facts:
            return ConflictStatus.CONSISTENT

        if self._settings is not None and getattr(self._settings, "llm_enabled", False):
            statements = "\n".join(f"- {f.statement}" for f in facts)
            prompt = (
                "Do these facts logically contradict each other? "
                "Reply with YES or NO only.\n\n" + statements
            )
            response = self._llm_call(prompt, temperature=0.1)
            if response and response.strip().upper().startswith("YES"):
                return ConflictStatus.CONFLICT

        return ConflictStatus.CONSISTENT

    # ------------------------------------------------------------------
    # Step 3: Causal branching
    # ------------------------------------------------------------------

    def _generate_alpha_branch(self, facts: List[Fact], claim: str) -> Branch:
        """Generate the high-confidence causal evolution path."""
        description = self._llm_call(
            f"Based on these facts, what is the MOST LIKELY evolution of: {claim}? "
            "(one sentence)\n\n"
            + "\n".join(f"- {f.statement}" for f in facts),
            temperature=0.3,
        ) or f"Current trends in '{claim}' continue along their established trajectory."

        return Branch(
            name="Alpha",
            description=description.strip(),
            probability=_ALPHA_PROBABILITY,
            key_assumption="Current trends continue",
        )

    def _generate_beta_branch(
        self, facts: List[Fact], claim: str, alpha: Branch
    ) -> Branch:
        """Generate the black-swan scenario where the Alpha assumption fails."""
        description = self._llm_call(
            f"If the key assumption '{alpha.key_assumption}' fails for '{claim}', "
            "what is the black swan scenario? (one sentence)",
            temperature=0.5,
        ) or f"A sudden reversal of key assumptions causes unexpected outcomes for '{claim}'."

        return Branch(
            name="Beta",
            description=description.strip(),
            probability=_BETA_PROBABILITY,
            key_assumption="Key assumption fails",
        )

    # ------------------------------------------------------------------
    # Step 4: Self-audit
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self, facts: List[Fact], conflict: ConflictStatus
    ) -> float:
        """Confidence = average fact confidence − conflict penalty."""
        if not facts:
            return 0.0
        avg = sum(f.confidence for f in facts) / len(facts)
        penalty = _CONFLICT_PENALTY if conflict == ConflictStatus.CONFLICT else 0.0
        return round(max(0.0, min(1.0, avg - penalty)), 4)

    def _identify_one_critical_gap(self, facts: List[Fact], claim: str) -> str:
        """Identify the single most critical missing data point."""
        result = self._llm_call(
            f"What is the SINGLE most critical missing data to analyze: {claim}? "
            "(one sentence)\n\n"
            + "\n".join(f"- {f.statement}" for f in facts),
            temperature=0.2,
        )
        return (result or f"Real-time quantitative data directly measuring '{claim}'.").strip()

    def _find_strongest_counter_arg(self, facts: List[Fact], claim: str) -> str:
        """Find the strongest counter-argument that could disprove the analysis."""
        result = self._llm_call(
            f"What is the STRONGEST counter-argument that could prove this analysis of "
            f"'{claim}' wrong? (100 words max)\n\n"
            + "\n".join(f"- {f.statement}" for f in facts),
            temperature=0.6,
        )
        return (result or f"Evidence for '{claim}' may be unrepresentative of underlying factors not yet in the knowledge graph.").strip()

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def llm_call(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        """Public entry point for single-prompt LLM calls.

        Returns the raw LLM response string, or *None* when no LLM is
        configured or the call fails.  Re-uses the same provider logic as
        the internal analysis steps.
        """
        return self._llm_call(prompt, temperature=temperature)

    def _llm_call(
        self, 
        prompt: str, 
        temperature: float = 0.2, 
        max_tokens: int = 1500,  # 确保接收这个参数
        response_format: str = "json"
    ) -> Optional[str]:
        """Unified LLM call dispatcher."""
        if self._client_type == "groq":
                # 只在这里返回，并确保带上 max_tokens
                return self._call_groq(prompt, temperature, max_tokens)
            
        if self._client_type == "openai":
                # 如果有 OpenAI，也记得传下去
                return self._call_openai(prompt, temperature, max_tokens)
                
            # 如果都不匹配，返回 None 或空
        return None
        
    # 修改 _call_groq 定义
    def _call_groq(self, prompt: str, temperature: float, max_tokens: int) -> Optional[str]:
        """Direct call to Groq API with reinforced constraints."""
        if not self._client:
            return None
        try:
            model_name = getattr(self._settings, "llm_model", "llama-3.1-8b-instant")
            chat_completion = self._client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,  # ✅ 这里的 max_tokens 现在是动态的 1500 了
                # 👇 强制 Groq 输出合法的 JSON 对象，不乱说话
                response_format={"type": "json_object"} 
            )
            return chat_completion.choices[0].message.content
        except Exception as exc:
            logger.error(f"Groq API call failed: {exc}")
            return None# ...
        

    

 

    def _llm_refine_facts(
        self,
        facts: List[Fact],
        news: List[str],
        graph: Dict[str, Any],
    ) -> List[Fact]:
        """Optional LLM pass to verify and refine extracted facts (no-op if LLM unavailable)."""
        # Placeholder: future LLM-based refinement can be added here
        return facts

    def _enrich_facts_with_entity_labels(
        self,
        facts: List[Fact],
        news: List[str],
    ) -> List[Fact]:
        """Enrich facts with three-layer entity context via EntityExtractionEngine.

        Each qualified fact whose statement matches an extracted entity gets its
        statement extended with a structured label tag::

            <entity> [LAYER1] functions as ROLE1/ROLE2 with VIRTUE1/VIRTUE2 nature

        Falls back silently if extraction fails or returns no entities.
        """
        try:
            from intelligence.entity_extraction import EntityExtractionEngine

            class _DirectLLMService:
                """Thin wrapper so EntityExtractionEngine can re-use the analyzer LLM."""
                def __init__(self, analyzer: "SacredSwordAnalyzer") -> None:
                    self._analyzer = analyzer

                def call(
                    self,
                    prompt: str,
                    temperature: float = 0.2,
                    max_tokens: int = 2000,
                    response_format: str = "json",
                ) -> str:
                    result = self._analyzer._llm_call(prompt, temperature=temperature)
                    return result or "[]"

            extractor = EntityExtractionEngine(_DirectLLMService(self))
            combined_text = "\n".join(news)
            entities = extractor.extract(combined_text, "sacred_sword_analysis")

            # Build a name → entity lookup for O(1) access
            entity_map = {e.name.lower(): e for e in entities}

            enriched: List[Fact] = []
            for fact in facts:
                statement_lower = fact.statement.lower()
                matched = next(
                    (e for name, e in entity_map.items() if name in statement_lower),
                    None,
                )
                if matched:
                    roles = "/".join(matched.structural_roles)
                    virtues = "/".join(matched.philosophical_nature)
                    label_tag = (
                        f" [{matched.physical_type}] functions as {roles}"
                        f" with {virtues} nature"
                    )
                    # Strip a single trailing period only (avoid removing dots from abbreviations)
                    base = fact.statement
                    if base.endswith("."):
                        base = base[:-1]
                    enriched.append(
                        Fact(
                            statement=base + label_tag,
                            source=fact.source,
                            confidence=fact.confidence,
                        )
                    )
                else:
                    enriched.append(fact)
            return enriched

        except Exception as exc:  # noqa: BLE001
            logger.warning("Entity label enrichment failed: %s", exc)
            return facts