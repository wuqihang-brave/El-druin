"""
experiments/backtest_evaluator.py
==================================
Historical backtesting framework for the EL-DRUIN prediction pipeline.

Evaluates the pipeline against 8 curated historical events with known outcomes,
computing direction accuracy, Brier scores, and attractor identification scores.
Optionally invokes an LLM advisory loop to suggest qualitative calibration
adjustments for mis-predicted events.

Usage
-----
    cd <repo-root>
    python experiments/backtest_evaluator.py [--llm-service <name>]

Outputs
-------
    experiments/backtest_results.json  — full per-event result dicts
    experiments/backtest_report.md     — human-readable Markdown table
    stdout                             — summary table
"""

from __future__ import annotations

import json
import math
import os
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup: allow importing from backend/ without installing the package
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

# ---------------------------------------------------------------------------
# Ground-truth dataset
# ---------------------------------------------------------------------------

# Each event entry contains:
#   excerpt      — news text fed to the pipeline
#   ground_truth — what actually materialised
#
# ground_truth fields:
#   realized_direction   — English display name of the dominant ontology pattern
#                          that best described the outcome (from pattern_i18n.py)
#   realized_outcome_ids — list of OUTCOME_CATALOG keys that actually materialized
#   outcome_realized     — bool: did the PRIMARY predicted trajectory materialise?
#   notes                — short explanation of what happened

BACKTEST_EVENTS: List[Dict[str, Any]] = [
    # ── 1. Hong Kong anti-extradition protests (2019) ──────────────────────
    {
        "id": "hk_protests_2019",
        "title": "Hong Kong Anti-Extradition Protests Escalate (June 2019)",
        "date": "2019-06-12",
        "excerpt": (
            "Hong Kong police fired tear gas and rubber bullets at thousands of protesters "
            "who surrounded the city's legislature on Wednesday, as demonstrators tried to block "
            "a second reading of a controversial extradition bill that would allow suspects to be "
            "sent for trial in mainland China. The clashes marked the most violent scenes in the "
            "financial hub in years. Organisers claimed more than a million people had marched "
            "peacefully the previous Sunday, while government supporters accused protesters of "
            "inciting violence. Chief Executive Carrie Lam suspended the bill's legislative "
            "process but refused to withdraw it entirely, prolonging a political crisis that "
            "would define Hong Kong's relationship with Beijing for years to come."
        ),
        "ground_truth": {
            "realized_direction": "Great-Power Coercion / Deterrence",
            "realized_outcome_ids": [
                "domestic_consolidation",
                "regime_change_attempt",
                "credibility_erosion",
                "counter_alliance_formation",
            ],
            "outcome_realized": True,
            "notes": (
                "Beijing ultimately imposed the National Security Law (2020), consolidating "
                "control over Hong Kong. Democratic institutions were dismantled. The coercion "
                "pattern fully materialised: domestic consolidation and credibility erosion of "
                "the 'one country two systems' framework."
            ),
        },
    },
    # ── 2. Wuhan COVID-19 outbreak (December 2019) ─────────────────────────
    {
        "id": "wuhan_covid_2019",
        "title": "Wuhan COVID-19 Outbreak Reported (December 2019)",
        "date": "2019-12-31",
        "excerpt": (
            "The World Health Organization's Country Office in China was informed of cases of "
            "pneumonia of unknown aetiology detected in Wuhan City, Hubei Province, China on "
            "31 December 2019. A total of 44 case-patients with pneumonia of unknown aetiology "
            "were reported to WHO between 31 December 2019 and 3 January 2020. Of the 44 "
            "case-patients, 11 were severely ill, while the remaining 33 patients were in "
            "stable condition. All patients were isolated and receiving treatment in Wuhan "
            "medical institutions. Chinese authorities identified a new type of coronavirus, "
            "which was isolated on 7 January 2020. The outbreak would subsequently spread "
            "globally and be declared a pandemic by March 2020."
        ),
        "ground_truth": {
            "realized_direction": "Single-Point Supply Chain Dependency",
            "realized_outcome_ids": [
                "supply_chain_fragmentation",
                "structural_disruption",
                "just_in_case_inventory_build",
                "near_shoring_acceleration",
                "supply_shock_vulnerability",
            ],
            "outcome_realized": True,
            "notes": (
                "The pandemic caused severe global supply chain disruption. Single-point "
                "dependencies on Chinese manufacturing were exposed. Firms shifted toward "
                "just-in-case inventory strategies and nearshoring. Structural disruption "
                "materialised across virtually all sectors."
            ),
        },
    },
    # ── 3. Russia full-scale invasion of Ukraine (February 2022) ───────────
    {
        "id": "russia_ukraine_invasion_2022",
        "title": "Russia Launches Full-Scale Invasion of Ukraine (February 2022)",
        "date": "2022-02-24",
        "excerpt": (
            "Russia launched a full-scale military invasion of Ukraine on Thursday, with "
            "President Vladimir Putin announcing a 'special military operation' in a pre-dawn "
            "television address. Explosions were heard in Kyiv, Kharkiv, Mariupol and other "
            "Ukrainian cities as Russian troops crossed the border from multiple directions "
            "including from Belarus to the north, Russia to the east and Russian-annexed "
            "Crimea to the south. Ukrainian President Volodymyr Zelensky declared martial law "
            "and appealed to citizens to defend the country. Western leaders condemned the "
            "attack as an unprovoked act of aggression and promised severe sanctions, while "
            "NATO activated its Response Force and reinforced its eastern flank."
        ),
        "ground_truth": {
            "realized_direction": "Interstate Military Conflict",
            "realized_outcome_ids": [
                "sanctions_escalation",
                "alliance_consolidation",
                "refugee_displacement",
                "energy_market_disruption",
                "arms_race_acceleration",
                "sanctions_cascade",
            ],
            "outcome_realized": True,
            "notes": (
                "Full-scale interstate military conflict materialised. The predicted "
                "sanctions cascade, NATO consolidation, and massive refugee displacement "
                "all occurred. Energy market disruption via Russian gas weaponisation "
                "further confirmed the trajectory."
            ),
        },
    },
    # ── 4. US chip export controls targeting China (October 2023) ──────────
    {
        "id": "us_china_chips_2023",
        "title": "US Expands Chip Export Controls Targeting China's AI Industry (October 2023)",
        "date": "2023-10-17",
        "excerpt": (
            "The Biden administration on Tuesday unveiled sweeping new export controls "
            "targeting China's ability to obtain advanced semiconductors and chipmaking "
            "equipment, expanding a crackdown begun a year ago. The rules tighten restrictions "
            "on Nvidia and AMD graphics processors used in artificial intelligence and "
            "supercomputing, lower the threshold for licensing requirements, and extend "
            "controls to 21 additional countries to prevent chips from reaching China through "
            "third parties. Commerce Secretary Gina Raimondo said the controls close loopholes "
            "that allowed China to import restricted chips through subsidiaries and foreign "
            "resellers."
        ),
        "ground_truth": {
            "realized_direction": "Entity-List Technology Blockade",
            "realized_outcome_ids": [
                "supply_chain_decoupling",
                "domestic_substitution_push",
                "technology_gap_widening",
                "parallel_tech_stack_emergence",
                "third_country_re-export",
            ],
            "outcome_realized": True,
            "notes": (
                "The entity-list technology blockade pattern fully materialised. China "
                "accelerated domestic chip programmes (Huawei Kirin, CXMT). Third-country "
                "re-export via Singapore, Malaysia, and UAE was subsequently documented. "
                "The technology gap in leading-edge nodes widened."
            ),
        },
    },
    # ── 5. Huawei entity list (May 2019) ───────────────────────────────────
    {
        "id": "huawei_ban_2019",
        "title": "Trump Administration Places Huawei on Export Blacklist (May 2019)",
        "date": "2019-05-16",
        "excerpt": (
            "The Trump administration placed Huawei Technologies on the Commerce Department's "
            "Entity List, effectively banning American companies from selling hardware and "
            "software to the Chinese telecommunications giant without government approval. "
            "The designation prevents US firms such as Google, Qualcomm, and Intel from "
            "supplying Huawei with products incorporating American technology, threatening "
            "to cut the company off from Android operating system updates and essential "
            "chipsets. Huawei warned that restrictions would harm US suppliers and the "
            "broader global technology ecosystem."
        ),
        "ground_truth": {
            "realized_direction": "Entity-List Technology Blockade",
            "realized_outcome_ids": [
                "domestic_substitution_push",
                "supply_chain_decoupling",
                "technology_gap_widening",
                "digital_sovereignty_push",
            ],
            "outcome_realized": True,
            "notes": (
                "Huawei developed its own HarmonyOS to replace Android and invested "
                "heavily in domestic chip design. Supply chain decoupling and domestic "
                "substitution materialised as predicted. The digital sovereignty push "
                "accelerated across Chinese tech sector."
            ),
        },
    },
    # ── 6. PLA Taiwan military drills (August 2022) ────────────────────────
    {
        "id": "taiwan_military_drills_2022",
        "title": "China Launches Military Exercises Around Taiwan in Response to Pelosi Visit (August 2022)",
        "date": "2022-08-04",
        "excerpt": (
            "China has begun unprecedented military exercises around Taiwan, firing ballistic "
            "missiles into surrounding waters in an angry response to US House Speaker Nancy "
            "Pelosi's visit to the island. China's Eastern Theater Command said it was "
            "conducting joint military exercises involving live fire in six zones surrounding "
            "Taiwan, closer to the island's shore than previous drills. The exercises, which "
            "included cyber attacks and air and naval deployments, were seen as China's most "
            "aggressive military manoeuvres near Taiwan since the 1990s."
        ),
        "ground_truth": {
            "realized_direction": "Great-Power Coercion / Deterrence",
            "realized_outcome_ids": [
                "military_deterrence_signal",
                "collective_defence_formation",
                "arms_race_acceleration",
                "credibility_erosion",
            ],
            "outcome_realized": True,
            "notes": (
                "The coercion/deterrence pattern materialised. US-Taiwan defence cooperation "
                "deepened after the drills. Japan announced increased defence spending. The "
                "drills normalised PLA air incursions into Taiwan's ADIZ, signalling a "
                "new baseline of military pressure."
            ),
        },
    },
    # ── 7. Brexit Withdrawal Agreement & Northern Ireland Protocol (December 2020) ──
    {
        "id": "brexit_withdrawal_2020",
        "title": (
            "UK and EU Finalise Brexit Withdrawal Agreement, "
            "Northern Ireland Protocol Triggers Political Crisis (December 2020)"
        ),
        "date": "2020-12-24",
        "excerpt": (
            "The United Kingdom and the European Union signed a landmark Trade and Cooperation "
            "Agreement on December 24, 2020, finalising the terms of Britain's departure from "
            "the EU's single market and customs union after more than four years of "
            "negotiations. The deal averted tariffs on goods trade but left significant "
            "barriers to services, which account for 80 percent of the UK economy. The most "
            "contentious element was the Northern Ireland Protocol, which kept the region "
            "aligned with EU single market rules for goods to avoid a hard border with the "
            "Republic of Ireland, effectively creating trade checks between Northern Ireland "
            "and mainland Britain. The Protocol immediately triggered a constitutional and "
            "political crisis, with Northern Ireland's unionist parties calling it a betrayal "
            "of British sovereignty. The Democratic Unionist Party threatened to collapse the "
            "Stormont power-sharing executive, while the EU and UK began a prolonged dispute "
            "over implementation that would strain bilateral relations for years."
        ),
        "ground_truth": {
            "realized_direction": "Trade War / Decoupling",
            "realized_outcome_ids": [
                "supply_chain_fragmentation",
                "structural_realignment",
                "regulatory_compliance_cost_spike",
                "multilateral_compliance_cost",
            ],
            "outcome_realized": True,
            "notes": (
                "Partial decoupling materialised: UK-EU trade volumes fell, services access "
                "was curtailed, and regulatory divergence created compliance cost spikes. "
                "The Northern Ireland Protocol dispute persisted until the Windsor Framework "
                "(2023), confirming prolonged structural realignment rather than clean "
                "separation or full reintegration."
            ),
        },
    },
    # ── 8. SCO expansion with Iran and Saudi Arabia (July 2023) ───────────
    {
        "id": "sco_expansion_2023",
        "title": "SCO Admits Iran as Full Member; Saudi Arabia Joins as Dialogue Partner (July 2023)",
        "date": "2023-07-04",
        "excerpt": (
            "The Shanghai Cooperation Organisation admitted Iran as a full member at its "
            "Heads of State summit in New Delhi on 4 July 2023, completing a transition that "
            "began in 2021. Saudi Arabia, the United Arab Emirates, Bahrain, Kuwait, the "
            "Maldives and Myanmar were simultaneously granted dialogue partner status, "
            "dramatically expanding the bloc's geographic and geopolitical reach. SCO "
            "Secretary-General Zhang Ming described the expansion as reflecting the "
            "organisation's growing appeal as an alternative multilateral forum to "
            "Western-dominated institutions. Analysts noted that Iran's accession, alongside "
            "the China-brokered normalisation of Saudi-Iranian relations in March 2023, "
            "signalled a deepening of non-Western multilateral integration and a potential "
            "challenge to US-led regional security architecture in both Central Asia and "
            "the Middle East."
        ),
        "ground_truth": {
            "realized_direction": "Formal Military Alliance",
            "realized_outcome_ids": [
                "counter_alliance_formation",
                "adversary_counter_coalition",
                "norm_cascade",
                "competing_norm_fragmentation",
            ],
            "outcome_realized": True,
            "notes": (
                "A counter-coalition to Western institutions materialised. SCO expansion "
                "combined with BRICS expansion (2023) and the China-brokered Saudi-Iran "
                "normalisation represents a concrete counter-alliance formation. Norm "
                "fragmentation between Western multilateralism and SCO/BRICS frameworks "
                "deepened."
            ),
        },
    },
]

# ---------------------------------------------------------------------------
# Domain similarity table (for partial direction_score matching)
# ---------------------------------------------------------------------------

_DOMAIN_MAP: Dict[str, str] = {
    "Great-Power Coercion / Deterrence": "coercion",
    "Hegemonic Sanctions": "coercion",
    "Multilateral Alliance Sanctions": "coercion",
    "Interstate Military Conflict": "military",
    "Formal Military Alliance": "military",
    "Non-State Armed Proxy Conflict": "military",
    "Entity-List Technology Blockade": "tech_blockade",
    "Tech Decoupling / Technology Iron Curtain": "tech_blockade",
    "Technology Standards Leadership": "tech_blockade",
    "Trade War / Decoupling": "trade",
    "Bilateral Trade Dependency": "trade",
    "Policy-Driven Trade Restriction": "trade",
    "Single-Point Supply Chain Dependency": "supply_chain",
    "Financial Isolation / SWIFT Cut-Off": "finance",
    "Central Bank Monetary Transmission": "finance",
    "Resource Dependency / Energy Weaponisation": "energy",
    "Information Warfare / Narrative Control": "information",
    "International Norm Construction": "norms",
}


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def direction_score(predicted_attractor: str, realized_direction: str) -> float:
    """Return 1.0 for exact match, 0.5 for same domain, 0.0 for miss."""
    if predicted_attractor == realized_direction:
        return 1.0
    pred_domain = _DOMAIN_MAP.get(predicted_attractor)
    real_domain = _DOMAIN_MAP.get(realized_direction)
    if pred_domain and real_domain and pred_domain == real_domain:
        return 0.5
    return 0.0


def brier_score(predicted_confidence: float, outcome_realized: bool) -> float:
    """Brier score = (p - outcome)^2.  Lower is better (0 = perfect, 1 = worst)."""
    outcome_val = 1.0 if outcome_realized else 0.0
    return (predicted_confidence - outcome_val) ** 2


def attractor_identification_score(
    attractors: List[str], realized_direction: str
) -> float:
    """1.0 if realized_direction in attractors, 0.5 if same domain, 0.0 if miss."""
    for att in attractors:
        if att == realized_direction:
            return 1.0
    for att in attractors:
        pred_domain = _DOMAIN_MAP.get(att)
        real_domain = _DOMAIN_MAP.get(realized_direction)
        if pred_domain and real_domain and pred_domain == real_domain:
            return 0.5
    return 0.0


def weighted_score(
    dir_score: float, brier: float, att_score: float
) -> float:
    """Combined score: 0.4 * direction + 0.3 * (1 - brier) + 0.3 * attractor."""
    return 0.4 * dir_score + 0.3 * (1.0 - brier) + 0.3 * att_score


# ---------------------------------------------------------------------------
# LLM-assisted calibration advisory (purely qualitative)
# ---------------------------------------------------------------------------

def suggest_calibration(
    event_id: str,
    eldruin_result: Dict[str, Any],
    ground_truth: Dict[str, Any],
    llm_service: Any,
) -> Optional[Dict[str, str]]:
    """Invoke LLM to suggest a qualitative confidence_prior calibration direction.

    The LLM is NOT allowed to output numbers.  It returns a direction
    ('increase' | 'decrease' | 'maintain') and a qualitative rationale.

    Returns None if llm_service is None or if the call fails.
    """
    if llm_service is None:
        return None

    predicted_dir = _top_attractor(eldruin_result)
    realized_dir = ground_truth.get("realized_direction", "unknown")
    notes = ground_truth.get("notes", "")

    prompt = textwrap.dedent(f"""
        You are a geopolitical analyst calibrating the EL-DRUIN ontological prediction model.

        Event ID: {event_id}
        Predicted dominant pattern: {predicted_dir}
        Actual realized direction:  {realized_dir}

        What actually happened:
        {notes}

        Given the discrepancy between predicted and realized directions, should the
        confidence_prior weight assigned to the pattern '{predicted_dir}' be:
          - increased (it should have fired more strongly for this type of event)
          - decreased (it over-fired or mis-fired)
          - maintained (the discrepancy is due to external factors, not the prior)

        IMPORTANT CONSTRAINTS:
        1. Do NOT output any numbers, percentages, or probability values.
        2. Give only: (a) 'increase', 'decrease', or 'maintain' as your direction,
           then (b) a 1-2 sentence qualitative rationale.
        3. Output in this exact format:
           DIRECTION: <increase|decrease|maintain>
           RATIONALE: <your rationale here>
    """).strip()

    try:
        response = llm_service.call(
            prompt=prompt,
            system=(
                "You are a model calibration advisor. Output only the requested format. "
                "Never output numbers, percentages, or probability values."
            ),
            temperature=0.2,
            max_tokens=200,
        )
        raw = str(response).strip()
        direction = "maintain"
        rationale = raw
        for line in raw.splitlines():
            if line.upper().startswith("DIRECTION:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in ("increase", "decrease", "maintain"):
                    direction = val
            elif line.upper().startswith("RATIONALE:"):
                rationale = line.split(":", 1)[1].strip()
        return {
            "event_id": event_id,
            "pattern": predicted_dir,
            "direction": direction,
            "rationale": rationale,
        }
    except Exception as exc:
        return {
            "event_id": event_id,
            "pattern": predicted_dir,
            "direction": "maintain",
            "rationale": f"LLM calibration call failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _top_attractor(result: Dict[str, Any]) -> str:
    """Extract the highest-confidence active pattern name from a pipeline result."""
    active = result.get("active_patterns", [])
    if not active:
        return "unknown"
    top = max(active, key=lambda p: p.get("confidence_prior", p.get("confidence", 0.0)))
    return top.get("pattern_name", top.get("pattern", "unknown"))


def _all_attractors(result: Dict[str, Any]) -> List[str]:
    """Return all active pattern names from a pipeline result."""
    active = result.get("active_patterns", [])
    return [p.get("pattern_name", p.get("pattern", "unknown")) for p in active]


def _composite_confidence(result: Dict[str, Any]) -> float:
    """Extract the composite confidence from a pipeline result."""
    conclusion = result.get("conclusion", {})
    if isinstance(conclusion, dict):
        conf = conclusion.get("confidence") or conclusion.get("final", {}).get(
            "overall_confidence"
        )
        if conf is not None:
            return float(conf)
    return 0.5


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------

@dataclass
class EventResult:
    event_id: str
    title: str
    top_attractor: str
    all_attractors: List[str]
    composite_conf: float
    dir_score: float
    brier: float
    att_score: float
    combined: float
    ground_truth: Dict[str, Any]
    eldruin_raw: Dict[str, Any]
    calibration_advisory: Optional[Dict[str, str]] = None
    error: Optional[str] = None


def _run_single_event(
    event: Dict[str, Any],
    llm_service: Any = None,
) -> EventResult:
    """Run the EL-DRUIN pipeline on a single event and score it."""
    from intelligence.evented_pipeline import run_evented_pipeline  # type: ignore

    event_id = event["id"]
    gt = event["ground_truth"]
    excerpt = event["excerpt"]

    try:
        pipeline_result = run_evented_pipeline(text=excerpt, llm_service=llm_service)
        result_dict = (
            pipeline_result
            if isinstance(pipeline_result, dict)
            else pipeline_result.__dict__
        )
    except Exception as exc:
        return EventResult(
            event_id=event_id,
            title=event["title"],
            top_attractor="error",
            all_attractors=[],
            composite_conf=0.5,
            dir_score=0.0,
            brier=1.0,
            att_score=0.0,
            combined=0.0,
            ground_truth=gt,
            eldruin_raw={},
            error=str(exc),
        )

    top_att = _top_attractor(result_dict)
    all_atts = _all_attractors(result_dict)
    conf = _composite_confidence(result_dict)
    realized_dir = gt["realized_direction"]
    outcome_realized = gt["outcome_realized"]

    d_score = direction_score(top_att, realized_dir)
    b_score = brier_score(conf, outcome_realized)
    a_score = attractor_identification_score(all_atts, realized_dir)
    w_score = weighted_score(d_score, b_score, a_score)

    calibration = None
    if (d_score < 1.0 or b_score > 0.1) and llm_service is not None:
        calibration = suggest_calibration(event_id, result_dict, gt, llm_service)

    return EventResult(
        event_id=event_id,
        title=event["title"],
        top_attractor=top_att,
        all_attractors=all_atts,
        composite_conf=conf,
        dir_score=d_score,
        brier=b_score,
        att_score=a_score,
        combined=w_score,
        ground_truth=gt,
        eldruin_raw=result_dict,
        calibration_advisory=calibration,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _result_to_dict(r: EventResult) -> Dict[str, Any]:
    return {
        "event_id": r.event_id,
        "title": r.title,
        "top_attractor": r.top_attractor,
        "all_attractors": r.all_attractors,
        "composite_confidence": round(r.composite_conf, 4),
        "scores": {
            "direction_score": round(r.dir_score, 4),
            "brier_score": round(r.brier, 4),
            "attractor_identification_score": round(r.att_score, 4),
            "combined_weighted_score": round(r.combined, 4),
        },
        "ground_truth": r.ground_truth,
        "calibration_advisory": r.calibration_advisory,
        "error": r.error,
    }


def _generate_markdown_report(results: List[EventResult]) -> str:
    lines = [
        "# EL-DRUIN Historical Backtesting Report",
        "",
        "Scoring formula: `0.4 × direction_score + 0.3 × (1 − brier_score) + 0.3 × attractor_score`",
        "",
        "| Event ID | Predicted Pattern | Realized Direction | Dir | Brier | Att | **Combined** |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        realized = r.ground_truth.get("realized_direction", "?")
        lines.append(
            f"| `{r.event_id}` "
            f"| {r.top_attractor} "
            f"| {realized} "
            f"| {r.dir_score:.2f} "
            f"| {r.brier:.3f} "
            f"| {r.att_score:.2f} "
            f"| **{r.combined:.3f}** |"
        )

    valid = [r for r in results if not r.error]
    if valid:
        avg_dir = sum(r.dir_score for r in valid) / len(valid)
        avg_brier = sum(r.brier for r in valid) / len(valid)
        avg_att = sum(r.att_score for r in valid) / len(valid)
        avg_combined = sum(r.combined for r in valid) / len(valid)
        lines += [
            f"| **AVERAGE ({len(valid)} events)** | — | — "
            f"| {avg_dir:.2f} "
            f"| {avg_brier:.3f} "
            f"| {avg_att:.2f} "
            f"| **{avg_combined:.3f}** |",
            "",
        ]

    lines += ["", "## Event Notes", ""]
    for r in results:
        lines.append(f"### `{r.event_id}`")
        if r.error:
            lines.append(f"**Error**: `{r.error}`")
        else:
            notes = r.ground_truth.get("notes", "")
            lines.append(f"**Realized outcome notes**: {notes}")
            if r.calibration_advisory:
                adv = r.calibration_advisory
                lines.append(
                    f"**LLM calibration advisory**: {adv.get('direction', '—')} "
                    f"confidence_prior for `{adv.get('pattern', '?')}`. "
                    f"Rationale: {adv.get('rationale', '—')}"
                )
        lines.append("")

    lines += [
        "---",
        "",
        "*Generated by `experiments/backtest_evaluator.py`. "
        "Ground-truth labels are curated from historical sources.*",
    ]
    return "\n".join(lines)


def _print_summary_table(results: List[EventResult]) -> None:
    col_w = [26, 28, 6, 6, 6, 9]
    header = (
        f"{'Event ID':<{col_w[0]}} "
        f"{'Top Predicted Pattern':<{col_w[1]}} "
        f"{'Dir':>{col_w[2]}} "
        f"{'Brier':>{col_w[3]}} "
        f"{'Att':>{col_w[4]}} "
        f"{'Combined':>{col_w[5]}}"
    )
    sep = "-" * (sum(col_w) + len(col_w))
    print("\n" + sep)
    print("EL-DRUIN BACKTESTING SUMMARY")
    print(sep)
    print(header)
    print(sep)
    for r in results:
        att_short = r.top_attractor[:col_w[1]]
        print(
            f"{r.event_id:<{col_w[0]}} "
            f"{att_short:<{col_w[1]}} "
            f"{r.dir_score:>{col_w[2]}.2f} "
            f"{r.brier:>{col_w[3]}.3f} "
            f"{r.att_score:>{col_w[4]}.2f} "
            f"{r.combined:>{col_w[5]}.3f}"
        )
    valid = [r for r in results if not r.error]
    if valid:
        print(sep)
        print(
            f"{'AVERAGE':<{col_w[0]}} "
            f"{'—':<{col_w[1]}} "
            f"{sum(r.dir_score for r in valid)/len(valid):>{col_w[2]}.2f} "
            f"{sum(r.brier for r in valid)/len(valid):>{col_w[3]}.3f} "
            f"{sum(r.att_score for r in valid)/len(valid):>{col_w[4]}.2f} "
            f"{sum(r.combined for r in valid)/len(valid):>{col_w[5]}.3f}"
        )
    print(sep + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_backtest(
    events: Optional[List[Dict[str, Any]]] = None,
    llm_service: Any = None,
    output_dir: Optional[Path] = None,
) -> List[EventResult]:
    """Run the full backtesting suite.

    Parameters
    ----------
    events:
        List of event dicts.  Defaults to BACKTEST_EVENTS.
    llm_service:
        Optional LLM service instance.  If None, deterministic fallback is used
        throughout and no calibration advisories are generated.
    output_dir:
        Directory for output files.  Defaults to experiments/ directory.

    Returns
    -------
    List of EventResult dataclasses, one per event.
    """
    if events is None:
        events = BACKTEST_EVENTS

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent

    results: List[EventResult] = []
    for evt in events:
        print(f"  [{evt['id']}] Running EL-DRUIN backtesting...", end=" ", flush=True)
        r = _run_single_event(evt, llm_service=llm_service)
        if r.error:
            print(f"ERROR: {r.error}")
        else:
            print(
                f"dir={r.dir_score:.2f}  brier={r.brier:.3f}  "
                f"att={r.att_score:.2f}  combined={r.combined:.3f}"
            )
        results.append(r)

    _print_summary_table(results)

    # Write results JSON
    results_path = output_dir / "backtest_results.json"
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump([_result_to_dict(r) for r in results], fh, indent=2, ensure_ascii=False)
    print(f"Results written to: {results_path}")

    # Write Markdown report
    report_path = output_dir / "backtest_report.md"
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(_generate_markdown_report(results))
    print(f"Report written to:  {report_path}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="EL-DRUIN Historical Backtesting Evaluator"
    )
    parser.add_argument(
        "--llm-service",
        default=None,
        help="LLM service name/config (leave blank to run deterministic-only mode)",
    )
    args = parser.parse_args()

    llm_svc = None
    if args.llm_service:
        try:
            from intelligence.llm_router import get_llm_service  # type: ignore
            llm_svc = get_llm_service(args.llm_service)
        except ImportError:
            print(
                "Warning: could not import llm_router; running in deterministic mode."
            )

    run_backtest(llm_service=llm_svc)
