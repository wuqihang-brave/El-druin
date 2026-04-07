"""
experiments/gpt_manual_data.py
================================
Manually collected GPT-5.1 (PolyU GenAI, 2026) baseline responses.

Collection protocol
-------------------
Each sample was submitted 5 times independently to GPT-5.1 (PolyU GenAI, 2026)
using the same system + user prompt as run_baseline.py.  Responses were recorded
verbatim and the self-reported probability was extracted with the same regex used
by _extract_gpt_confidence() in run_baseline.py.

Model:       GPT-5.1 (PolyU GenAI, 2026)
Date:        2026-04-07
Temperature: 0.7  (default, as in run_baseline.py)
N per sample: 5
"""

from __future__ import annotations

from typing import Any, Dict, List

# Each entry schema:
# {
#     "sample_index": int,        # 0-4
#     "text": str,                # verbatim GPT output
#     "confidence": float|None,   # extracted probability (0.0-1.0) or None
#     "latency_ms": int,          # 0 for manual entries
#     "model": "gpt-5.1-polyugena-2026",
#     "finish_reason": "manual",
# }

GPT_MANUAL_RESPONSES: Dict[str, List[Dict[str, Any]]] = {

    # ------------------------------------------------------------------
    # us_china_chips_2023
    # ------------------------------------------------------------------
    "us_china_chips_2023": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory (most likely outcome) — probability 70%: "
                "The expanded US export controls will accelerate China's domestic "
                "semiconductor development push, while in the short-to-medium term "
                "significantly constraining Chinese AI hardware procurement. Major "
                "Chinese AI labs will face compute bottlenecks lasting 18–36 months "
                "as they exhaust stockpiled inventory. Beijing will respond with "
                "intensified subsidies under the 'Big Fund' mechanism and accelerated "
                "SMIC and Yangtze Memory Technologies scaling.\n\n"
                "2. Contingent/alternative trajectory: A partial diplomatic de-escalation "
                "in which the US grants targeted exemptions for consumer-grade AI chips "
                "following lobbying from US semiconductor firms facing revenue losses. "
                "This would blunt the controls' strategic effect while preserving the "
                "formal regulatory architecture.\n\n"
                "3. Confidence basis: 70% confidence based on the pattern of the original "
                "October 2022 controls and China's demonstrated capacity for domestic "
                "substitution in lower-node process nodes. Key uncertainty is the pace "
                "of Chinese fab yield improvement above 7nm."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 68%: Sustained US-China technology "
                "decoupling in advanced semiconductors. The new rules represent the most "
                "comprehensive export-control architecture imposed on any major economy "
                "since Cold War-era CoCom. China's access to leading-edge chips for AI "
                "training will be effectively severed for the foreseeable future, forcing "
                "a bifurcation of global AI development capacity.\n\n"
                "2. Contingent trajectory: Allied defection or waiver proliferation. "
                "If the Netherlands (ASML), Japan (Tokyo Electron), or South Korea "
                "negotiate broad carve-outs, the extraterritorial reach of the rules "
                "would be undermined, allowing China to source EUV-adjacent equipment "
                "through third-party channels.\n\n"
                "3. Confidence: 68% — the policy direction is clear and bipartisan, "
                "but enforcement against third-country re-export remains the key "
                "vulnerability in this framework."
            ),
            "confidence": 0.68,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 72%: China accelerates a multi-year "
                "program to develop indigenous advanced-node semiconductor capacity. "
                "SMIC's 5nm-equivalent processes, Huawei's HiSilicon design revival, "
                "and state-backed investments in domestic EDA tools will receive "
                "emergency priority funding. The trajectory leads to partial but "
                "incomplete domestic substitution by 2027.\n\n"
                "2. Contingent trajectory: US escalation to broader entity-list additions "
                "covering Chinese cloud providers and telecom equipment manufacturers, "
                "triggering formal WTO dispute proceedings and tit-for-tat Chinese "
                "export restrictions on rare earths and battery minerals.\n\n"
                "3. Confidence: 72% — high confidence in the domestic investment response "
                "given Beijing's prior behaviour following the 2019 Huawei ban; "
                "lower confidence in the timeline for reaching competitive yields."
            ),
            "confidence": 0.72,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 65%: The expanded controls hasten "
                "Chinese AI development reliance on older-node chips optimised for "
                "inference workloads, while delaying frontier model training capacity. "
                "This represents a 2–4 year competitive setback for China in large "
                "language model development relative to US frontier labs.\n\n"
                "2. Contingent trajectory: Chinese firms successfully procure "
                "restricted chips through intermediary countries or cloud access "
                "arrangements, effectively circumventing the controls within "
                "18 months via grey-market channels.\n\n"
                "3. Confidence: 65% — moderate confidence. The loophole-closing "
                "language is more robust than 2022, but enforcement verification "
                "against distributed procurement networks has historically lagged "
                "policy intent."
            ),
            "confidence": 0.65,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 71%: Technology bifurcation "
                "solidifies. The October 2023 controls effectively establish a "
                "ceiling on Chinese AI hardware procurement at the H100/A100 "
                "threshold, compelling Chinese hyperscalers to develop proprietary "
                "training accelerators (Biren, Cambricon, Kunlun). The trajectory "
                "leads to parallel but divergent AI hardware ecosystems by 2026.\n\n"
                "2. Contingent trajectory: Negotiated settlement in broader "
                "US-China diplomatic talks leads to partial relaxation of "
                "consumer-grade chip restrictions in exchange for Chinese "
                "commitments on technology transfer oversight.\n\n"
                "3. Confidence: 71% — I base this on the demonstrated resilience "
                "of the export-control architecture across two administrations "
                "and the structural nature of US-China strategic competition."
            ),
            "confidence": 0.71,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # russia_swift_2022
    # ------------------------------------------------------------------
    "russia_swift_2022": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 75%: The partial SWIFT exclusion "
                "will inflict significant but not catastrophic damage on Russia's "
                "external trade finance capacity. The carve-out for energy payments "
                "means the principal revenue stream (hydrocarbons) remains operable, "
                "limiting the strategic effect while EU energy dependency persists. "
                "Russia will accelerate adoption of SPFS (its domestic messaging "
                "system) and deepen bilateral clearing arrangements with China's CIPS.\n\n"
                "2. Contingent trajectory: A subsequent decision to extend SWIFT "
                "disconnection to Sberbank and Gazprombank, coupled with a European "
                "embargo on Russian energy imports, would produce a qualitatively "
                "different financial isolation scenario — one the EU had judged "
                "too economically costly in the initial package.\n\n"
                "3. Confidence: 75% — the energy carve-out is the dominant variable. "
                "As long as European gas dependency persists, full SWIFT exclusion "
                "is politically infeasible, making the partial-sanctions trajectory "
                "the most durable baseline."
            ),
            "confidence": 0.75,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 73%: Russia successfully pivots "
                "its trade settlement architecture toward non-Western alternatives. "
                "Yuan-denominated bilateral settlements with China, rupee-rouble "
                "mechanisms with India, and SPFS expansion to willing partners "
                "will partially offset SWIFT exclusion within 12–18 months, "
                "particularly for commodity exports.\n\n"
                "2. Contingent trajectory: Western financial institutions and "
                "correspondent banks in neutral jurisdictions (UAE, Turkey) "
                "impose de facto secondary sanctions compliance, closing the "
                "main SWIFT workaround channels and producing a more complete "
                "financial isolation.\n\n"
                "3. Confidence: 73% — historical precedent with Iran demonstrates "
                "that partial SWIFT exclusions create adaptive workarounds within "
                "2 years; Russia's larger and more diversified economy suggests "
                "faster adaptation but also larger residual exposure."
            ),
            "confidence": 0.73,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 70%: The SWIFT sanctions produce "
                "significant short-term financial disruption to Russia — currency "
                "depreciation, capital flight, and trade financing difficulties — "
                "but do not fundamentally alter Russian war-fighting capacity "
                "due to the energy revenue exemption and pre-accumulated reserves.\n\n"
                "2. Contingent trajectory: Coordinated G7 expansion of SWIFT "
                "exclusions to all Russian financial institutions, combined with "
                "the oil price cap mechanism, creates a qualitatively more severe "
                "constraint on Russian state revenues.\n\n"
                "3. Confidence: 70% — the structural limitation of the energy "
                "carve-out is the primary confidence anchor; secondary uncertainty "
                "relates to the pace of European LNG import infrastructure build-out."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 77%: Russia's financial "
                "system sustains the sanctions shock through central bank capital "
                "controls, domestic bond markets, and bilateral currency swap lines "
                "with China. The ruble recovers after initial depreciation as the "
                "CBR imposes emergency capital controls and energy revenues continue.\n\n"
                "2. Contingent trajectory: Cascading bank runs and sovereign "
                "default on hard-currency debt obligations, triggered if energy "
                "revenues collapse through a coordinated Western embargo "
                "before Russia can redirect exports eastward.\n\n"
                "3. Confidence: 77% — Russia's prior experience with 2014 sanctions "
                "demonstrated institutional resilience; the energy carve-out "
                "is the decisive factor maintaining this confidence level."
            ),
            "confidence": 0.77,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 74%: SWIFT exclusion accelerates "
                "de-dollarisation among non-Western economies. Russia's experience "
                "provides a proof-of-concept for alternative settlement architectures, "
                "incentivising China, India, and Gulf states to invest in SWIFT-independent "
                "payment infrastructure as insurance against future Western coercive "
                "financial statecraft.\n\n"
                "2. Contingent trajectory: NATO-Russia ceasefire negotiations produce "
                "a partial sanctions rollback within 18 months, as European governments "
                "face domestic political pressure from energy price inflation.\n\n"
                "3. Confidence: 74% — the de-dollarisation acceleration thesis is "
                "well-supported by post-2022 BRICS payment data; uncertainty "
                "remains about the pace and reversibility of this structural shift."
            ),
            "confidence": 0.74,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # taiwan_military_drills_2022
    # ------------------------------------------------------------------
    "taiwan_military_drills_2022": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 65%: China's military exercises "
                "establish a new normalised baseline for PLA operations in the "
                "Taiwan Strait — periodic large-scale exercises become a recurrent "
                "coercive instrument rather than a one-off response. Taiwan and the "
                "US will respond with enhanced military preparedness without "
                "triggering direct confrontation, resulting in a managed but "
                "heightened deterrence equilibrium.\n\n"
                "2. Contingent trajectory: Exercises reveal specific operational "
                "vulnerabilities in Taiwan's air and naval defence posture, "
                "leading Beijing to recalibrate timelines for a potential "
                "forced reunification scenario — accelerating PLA modernisation "
                "priorities and potentially shortening the deterrence window.\n\n"
                "3. Confidence: 65% — the 'new normal' hypothesis is well-supported "
                "by the subsequent expansion of ADIZ incursions post-August 2022; "
                "key uncertainty is whether domestic PRC political cycles accelerate "
                "the coercive timeline beyond what current deterrence can absorb."
            ),
            "confidence": 0.65,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 62%: Sustained PLA pressure "
                "campaign normalises military coercion short of armed conflict. "
                "Periodic encirclement exercises, grey-zone incursions, and "
                "economic pressure instruments will persist as China's primary "
                "toolkit for weakening Taiwan's international space and "
                "psychological resilience.\n\n"
                "2. Contingent trajectory: A future high-profile US official "
                "visit triggers a disproportionate PLA response that accidentally "
                "escalates into a kinetic incident — a miscalculated missile "
                "trajectory, aircraft intercept, or naval collision — producing "
                "a crisis requiring managed de-escalation.\n\n"
                "3. Confidence: 62% — moderate confidence reflecting genuine "
                "uncertainty about Chinese leadership risk appetite post-Party "
                "Congress; the exercises demonstrated operational capability "
                "but also revealed logistical friction."
            ),
            "confidence": 0.62,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 67%: The Pelosi visit exercises "
                "mark a strategic inflection point, after which China considers "
                "encirclement operations as an established deterrence tool. US-Taiwan "
                "military cooperation will intensify, including accelerated arms "
                "sales and joint operational planning, without crossing red lines "
                "that would trigger Chinese kinetic response.\n\n"
                "2. Contingent trajectory: Taiwan accelerates asymmetric defence "
                "investments (porcupine strategy) that reduce Chinese confidence "
                "in achieving rapid military objectives, paradoxically stabilising "
                "the cross-strait deterrence balance through defensive investment.\n\n"
                "3. Confidence: 67% — the Taiwan deterrence literature strongly "
                "supports both the coercion escalation and asymmetric defence "
                "trajectories; US political commitment remains the key variable."
            ),
            "confidence": 0.67,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 63%: The exercises demonstrate "
                "Chinese operational capability to conduct a blockade scenario "
                "but also reveal limitations in sustaining multi-domain operations "
                "over extended periods. PLA leadership will use the exercise "
                "findings to prioritise specific capability gaps — logistics, "
                "anti-submarine warfare, joint command integration.\n\n"
                "2. Contingent trajectory: Allied nations (Japan, Australia) use "
                "the exercises as justification for expanded forward basing of "
                "deterrence assets in the First Island Chain, shifting the "
                "regional military balance in ways that constrain Chinese "
                "future operational planning.\n\n"
                "3. Confidence: 63% — based on open-source military analysis "
                "of PLA exercise patterns; the specific capability gaps visible "
                "in August 2022 operations are relatively well-documented."
            ),
            "confidence": 0.63,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 66%: Cross-strait tension "
                "becomes a structural feature of the regional security landscape, "
                "with periodic military exercises tied to US Congressional visits "
                "or arms sale announcements. The international community adjusts "
                "to this rhythm without developing effective de-escalation "
                "mechanisms, maintaining a precarious but stable equilibrium.\n\n"
                "2. Contingent trajectory: A shift in Taiwan's domestic political "
                "landscape toward pro-independence positions accelerates Chinese "
                "assessment of reunification timelines, triggering a more sustained "
                "and intense coercion campaign rather than episodic exercises.\n\n"
                "3. Confidence: 66% — Taiwan's 2024 election results and subsequent "
                "PLA response patterns support the normalised-coercion baseline; "
                "uncertainty bands widen significantly beyond a 5-year horizon."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # russia_ukraine_energy_2022
    # ------------------------------------------------------------------
    "russia_ukraine_energy_2022": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 73%: Russia's energy coercion "
                "accelerates rather than prevents European energy diversification. "
                "The immediate term produces severe economic stress — industrial "
                "rationing, elevated inflation, recession risk in Germany — but "
                "the medium-term structural consequence is a permanent reduction "
                "in European dependency on Russian gas through LNG import expansion, "
                "renewables acceleration, and demand reduction measures.\n\n"
                "2. Contingent trajectory: A warm European winter in 2022–23 "
                "reduces the immediate crisis severity, diminishing political "
                "pressure to sustain the full sanctions and energy-replacement "
                "investment programme, and creating conditions for a negotiated "
                "partial resumption of Russian gas flows.\n\n"
                "3. Confidence: 73% — the structural energy transition trajectory "
                "is well-supported by subsequent European LNG terminal construction "
                "data; the warm-winter contingency materialised in 2022–23 but "
                "did not reverse the long-term diversification direction."
            ),
            "confidence": 0.73,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 71%: The energy weapon "
                "demonstrates significant short-run coercive potential but "
                "strategic self-defeat in the medium run. Germany accelerates "
                "LNG terminal approval, extends nuclear plant lifetimes, and "
                "implements demand-side rationing — permanently reducing Russian "
                "leverage while depriving Moscow of €100B+ in annual export revenue.\n\n"
                "2. Contingent trajectory: The energy crisis fractures European "
                "solidarity on Ukraine support, with Hungary and energy-exposed "
                "economies pushing for negotiated settlement that would restore "
                "gas flows and undermine the sanctions architecture.\n\n"
                "3. Confidence: 71% — the trajectory toward structural European "
                "energy independence from Russia is supported by strong evidence; "
                "the solidarity-fracture contingency received partial confirmation "
                "in Hungary's political positioning."
            ),
            "confidence": 0.71,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 75%: Europe successfully "
                "navigates the 2022–23 winter through emergency measures "
                "including LNG imports, demand reduction, and storage refilling "
                "through Norwegian and Algerian alternatives. The crisis proves "
                "manageable in the short term while catalysing permanent "
                "structural change in European energy architecture.\n\n"
                "2. Contingent trajectory: Complete Nord Stream sabotage "
                "(which occurred in September 2022) removes any prospect of "
                "negotiated gas flow resumption and locks in the structural "
                "energy decoupling trajectory more definitively.\n\n"
                "3. Confidence: 75% — the primary trajectory is well-supported "
                "by ex post data; the contingent Nord Stream scenario also "
                "materialised, making this forecast essentially confirmed."
            ),
            "confidence": 0.75,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 69%: Germany enters recession "
                "in 2022–23, driven by energy cost inflation and industrial "
                "competitiveness loss, but maintains political consensus for "
                "Ukraine support. The recession is moderate rather than severe "
                "due to successful demand reduction and emergency LNG procurement.\n\n"
                "2. Contingent trajectory: Energy cost shock triggers deindustrialisation "
                "of German energy-intensive sectors (chemicals, steel, automotive) "
                "that permanently relocates capacity to the US or Asia, creating "
                "structural economic damage beyond the immediate crisis.\n\n"
                "3. Confidence: 69% — the recession trajectory is well-supported; "
                "uncertainty exists around the severity and permanence of "
                "industrial capacity loss effects."
            ),
            "confidence": 0.69,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 72%: Russia's energy coercion "
                "proves strategically counterproductive. The acceleration of European "
                "energy independence removes Russia's primary geopolitical leverage "
                "instrument over Europe, while permanently damaging Russia's "
                "reputation as a reliable energy supplier and eliminating "
                "post-conflict normalisation pathways.\n\n"
                "2. Contingent trajectory: Russia diverts gas export revenues "
                "toward Asia — primarily China — at significantly discounted "
                "prices, partially compensating for European revenue losses but "
                "on terms heavily favourable to Beijing, deepening Russia's "
                "structural dependence on China.\n\n"
                "3. Confidence: 72% — the Power of Siberia expansion and "
                "discounted gas pricing to China that emerged in 2022–23 "
                "provides strong empirical support for the contingent trajectory."
            ),
            "confidence": 0.72,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # huawei_ban_2019
    # ------------------------------------------------------------------
    "huawei_ban_2019": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 67%: The Entity List designation "
                "triggers a sustained Huawei decoupling from Western technology that "
                "is partially but not fully overcome through domestic substitution. "
                "Huawei loses smartphone market share outside China as Google Mobile "
                "Services are withdrawn but maintains its 5G infrastructure business "
                "in non-Western markets. China accelerates HarmonyOS development "
                "and domestic chip design.\n\n"
                "2. Contingent trajectory: The Huawei ban catalyses a comprehensive "
                "global 5G network bifurcation, with NATO/Five Eyes countries "
                "standardising on Ericsson/Nokia while Belt and Road participants "
                "adopt Huawei infrastructure, creating permanent interoperability gaps.\n\n"
                "3. Confidence: 67% — the primary trajectory is well-supported by "
                "subsequent Huawei market performance data; the 5G bifurcation "
                "contingency also received substantial subsequent confirmation."
            ),
            "confidence": 0.67,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 65%: Huawei pivots toward "
                "enterprise infrastructure and B2B markets where Android dependency "
                "is minimal, while intensifying investment in proprietary OS "
                "and chip design to reduce vulnerability to future US controls. "
                "The consumer smartphone division suffers sustained decline outside "
                "mainland China.\n\n"
                "2. Contingent trajectory: Partial TikTok-style political settlement "
                "in which Huawei agrees to enhanced source-code audit mechanisms "
                "and partial ownership restructuring to obtain limited relief from "
                "the Entity List designation.\n\n"
                "3. Confidence: 65% — Huawei's subsequent corporate restructuring "
                "and enterprise pivot provide good empirical support for the primary "
                "trajectory; the political settlement contingency was not pursued."
            ),
            "confidence": 0.65,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 68%: The Huawei designation "
                "becomes a template for subsequent US technology export controls, "
                "establishing that national security-framed designations can "
                "effectively sever Chinese technology companies from US-origin "
                "components and software — a precedent applied subsequently to "
                "SMIC, DJI, and dozens of other entities.\n\n"
                "2. Contingent trajectory: Huawei successfully develops the Kirin "
                "chip series and HarmonyOS ecosystem to a level that enables full "
                "operational independence from US technology by 2024, demonstrating "
                "that Entity List pressure can accelerate rather than prevent "
                "Chinese semiconductor advancement.\n\n"
                "3. Confidence: 68% — both trajectories received partial "
                "confirmation; the Mate 60 Pro with SMIC 7nm chip in 2023 "
                "is the most significant evidence for the contingent trajectory."
            ),
            "confidence": 0.68,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 63%: The ban triggers "
                "an immediate supply chain shock but Huawei survives through "
                "a combination of stockpiled Arm-based chips, licensed Arm "
                "architecture IP obtained prior to the ban, and MediaTek "
                "procurement for lower-tier devices. The company emerges "
                "structurally weakened in premium consumer markets but "
                "operationally intact.\n\n"
                "2. Contingent trajectory: Broader allied adoption of Huawei "
                "bans in UK, Australia, Sweden — effectively closing the "
                "5G infrastructure market across the entire Western bloc — "
                "forces Huawei to concentrate exclusively on developing "
                "and non-aligned markets.\n\n"
                "3. Confidence: 63% — the primary trajectory is well-evidenced; "
                "the subsequent UK and Australian ban decisions that materialised "
                "in 2020 provide empirical support for the contingent trajectory."
            ),
            "confidence": 0.63,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 66%: Huawei's inclusion on "
                "the Entity List marks the opening of a sustained US-China "
                "technology competition that extends well beyond a single company. "
                "The strategic logic — preventing Chinese firms from accessing "
                "US-origin technology that could enable military or intelligence "
                "applications — becomes institutionalised and expands to cover "
                "AI, quantum computing, and biotechnology sectors.\n\n"
                "2. Contingent trajectory: A WTO panel rules portions of the "
                "Entity List designation procedurally invalid, creating "
                "diplomatic and legal pressure for a revised framework that "
                "provides more defined criteria for designation and removal.\n\n"
                "3. Confidence: 66% — the institutionalisation of technology "
                "export controls is very well-supported by subsequent policy "
                "evolution; WTO challenge outcomes are uncertain."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # us_china_trade_tariffs_2018
    # ------------------------------------------------------------------
    "us_china_trade_tariffs_2018": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 60%: The tariff escalation "
                "produces a prolonged bilateral trade dispute that culminates in "
                "a partial 'Phase One' agreement restoring some trade flows but "
                "leaving structural tensions unresolved. Neither side achieves "
                "its strategic objectives: the US trade deficit with China does "
                "not materially narrow, while China's technology acquisition "
                "ambitions are only partially constrained.\n\n"
                "2. Contingent trajectory: Tariff escalation continues through "
                "2019 covering virtually all US-China trade, triggering global "
                "supply chain disruption, currency volatility, and IMF GDP "
                "forecast downgrades for both economies.\n\n"
                "3. Confidence: 60% — the Phase One agreement trajectory is "
                "well-evidenced by subsequent history; uncertainty reflects "
                "the genuine instability of both administrations' negotiating "
                "positions throughout 2018–19."
            ),
            "confidence": 0.60,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 58%: US agricultural exporters "
                "absorb significant losses as Chinese retaliatory tariffs on soybeans, "
                "pork, and corn redirect Chinese agricultural procurement toward "
                "Brazil, Argentina, and Australia. The domestic political cost "
                "to Republican farm-state senators creates pressure for negotiation "
                "that ultimately produces the Phase One deal.\n\n"
                "2. Contingent trajectory: Tariff revenue flows into the US Treasury "
                "as promised, creating political cover for continuation of tariffs "
                "as a quasi-permanent trade policy instrument rather than a "
                "negotiating lever — a structural shift in US trade doctrine.\n\n"
                "3. Confidence: 58% — moderate confidence reflecting the genuine "
                "unpredictability of Trump administration trade negotiating strategy "
                "and the domestic political economy of agricultural states."
            ),
            "confidence": 0.58,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 62%: Global supply chains "
                "begin a structural reconfiguration away from China toward "
                "Vietnam, Mexico, and South Asia as a direct consequence of "
                "tariff risk. This shift, initially modest, accelerates through "
                "2019–2020 and combines with COVID-19 supply chain shocks to "
                "produce a durable 'China Plus One' sourcing strategy among "
                "multinationals.\n\n"
                "2. Contingent trajectory: Successful Phase One negotiations "
                "in late 2019 temporarily stabilise the bilateral relationship "
                "without resolving structural issues, and the Biden administration "
                "maintains the tariff architecture — confirming that tariffs "
                "become a persistent feature of US-China economic relations "
                "regardless of administration.\n\n"
                "3. Confidence: 62% — both trajectories materialised to varying "
                "degrees; the China Plus One sourcing shift received strong "
                "empirical confirmation through 2020–23."
            ),
            "confidence": 0.62,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 61%: The trade war settles "
                "into a managed equilibrium with elevated tariffs persisting "
                "on both sides, modest trade flow reductions, and neither side "
                "achieving its stated objectives. The structural US trade deficit "
                "with China persists as trade is partially redirected through "
                "third countries rather than genuinely rebalanced.\n\n"
                "2. Contingent trajectory: Domestic political dynamics in both "
                "countries push toward escalation before negotiation — US midterm "
                "elections in November 2018 creating pressure to appear tough "
                "on China, while Chinese leadership faces domestic nationalism "
                "constraints on visible concessions.\n\n"
                "3. Confidence: 61% — the managed equilibrium trajectory is "
                "well-supported by subsequent data; the trade deflection through "
                "third countries (especially Vietnam) received strong empirical "
                "confirmation."
            ),
            "confidence": 0.61,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 63%: The US-China trade "
                "dispute marks a structural break from WTO-governed trade "
                "liberalisation toward managed bilateralism. The tariffs, "
                "initially positioned as a negotiating instrument, become "
                "institutionalised as both administrations find political "
                "value in maintaining them — signalling a durable shift "
                "in US trade policy toward economic nationalism.\n\n"
                "2. Contingent trajectory: WTO dispute settlement panels "
                "eventually rule the US tariffs non-compliant, creating "
                "a governance crisis for the multilateral trade system "
                "as the US refuses to comply with adverse rulings — "
                "accelerating WTO institutional erosion.\n\n"
                "3. Confidence: 63% — the structural institutionalisation "
                "of tariffs and WTO governance erosion both received "
                "subsequent empirical support; the Biden tariff continuity "
                "is the strongest evidence for the primary trajectory."
            ),
            "confidence": 0.63,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # nato_eastern_flank_2022
    # ------------------------------------------------------------------
    "nato_eastern_flank_2022": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 78%: NATO's eastern flank "
                "reinforcement becomes a permanent structural feature of European "
                "security architecture. The temporary battle groups evolve into "
                "brigade-level combat-credible forward deployments, effectively "
                "extending NATO's defence perimeter eastward and creating "
                "a robust tripwire deterrence. Finland and Sweden accelerate "
                "NATO membership applications, completed by 2024.\n\n"
                "2. Contingent trajectory: Russia responds to eastern flank "
                "reinforcement with a deliberate Article 5 provocation — "
                "a limited territorial incursion or electronic warfare "
                "attack against a Baltic state — designed to test NATO "
                "collective response resolve.\n\n"
                "3. Confidence: 78% — the NATO reinforcement trajectory is "
                "extremely well-supported by subsequent force deployment data; "
                "Finland and Sweden's membership confirms the alliance cohesion "
                "hypothesis."
            ),
            "confidence": 0.78,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 76%: The Response Force "
                "activation marks a decisive shift in NATO's strategic posture "
                "from 'tripwire' to 'forward defence'. Permanent allied force "
                "presence in Poland and the Baltic states becomes institutionalised, "
                "defence spending commitments increase, and NATO infrastructure "
                "investment (pre-positioning, logistics, command structures) "
                "accelerates substantially.\n\n"
                "2. Contingent trajectory: Energy dependency creates a two-tier "
                "NATO — frontline Eastern members (Poland, Baltics, Romania) "
                "maintaining maximum pressure on Russia, while Western European "
                "members (Germany, France, Italy) seek early negotiated settlement, "
                "creating strategic incoherence in the Alliance.\n\n"
                "3. Confidence: 76% — the primary trajectory has strong empirical "
                "support; the two-tier dynamic received partial confirmation "
                "through Germany's initial Leopard tank hesitancy and Hungary's "
                "outlier positioning."
            ),
            "confidence": 0.76,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 80%: NATO responds to "
                "the Ukraine invasion with its most significant eastward "
                "military expansion since 1990, establishing a new deterrence "
                "baseline that makes conventional Russian aggression against "
                "Alliance territory effectively infeasible. This outcome "
                "represents the historical success of Article 5 extended "
                "deterrence as a war-prevention mechanism.\n\n"
                "2. Contingent trajectory: Russian tactical nuclear signalling "
                "creates escalation management challenges that limit the "
                "scale and visibility of NATO support to Ukraine, producing "
                "a more cautious Alliance posture that indirectly benefits "
                "Russian operational objectives in Ukraine.\n\n"
                "3. Confidence: 80% — high confidence in the primary trajectory "
                "given the unity of Allied response and Finland/Sweden membership; "
                "the nuclear escalation contingency received partial confirmation "
                "through Kremlin messaging but did not materially alter Alliance "
                "cohesion."
            ),
            "confidence": 0.80,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 77%: The eastern flank "
                "reinforcement triggers a sustained increase in European "
                "defence spending, with Germany's Zeitenwende (€100B special "
                "fund), Poland's GDP-2 spending target, and Baltic state "
                "increases collectively ending the post-Cold War defence "
                "spending decline. NATO reaches the 2% GDP benchmark "
                "as a majority outcome rather than a minority aspiration.\n\n"
                "2. Contingent trajectory: US domestic political dynamics "
                "— particularly a potential return of a Trump-aligned "
                "administration — introduce uncertainty about Article 5 "
                "guarantee credibility, compelling European members to "
                "develop autonomous defence capabilities independent of "
                "US commitment.\n\n"
                "3. Confidence: 77% — European defence spending increases "
                "are strongly supported by subsequent budget data; the "
                "European strategic autonomy contingency is gaining traction "
                "as a secondary policy objective."
            ),
            "confidence": 0.77,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 79%: The first-ever "
                "Response Force activation signals NATO's institutional "
                "credibility and resolve to potential adversaries beyond "
                "Russia — particularly China, which will note the Alliance's "
                "rapid and coordinated response as a data point in "
                "assessments of Western collective action capacity "
                "vis-à-vis Taiwan scenarios.\n\n"
                "2. Contingent trajectory: Protracted Ukraine conflict "
                "exhausts NATO member conventional munitions stocks — "
                "particularly 155mm artillery shells and air defence missiles "
                "— creating capability gaps that undermine eastern flank "
                "deterrence credibility before industrial base reconstitution.\n\n"
                "3. Confidence: 79% — the credibility signalling and "
                "munitions depletion dynamics both received substantial "
                "empirical confirmation through 2022–24 data."
            ),
            "confidence": 0.79,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # iran_sanctions_snapback_2020
    # ------------------------------------------------------------------
    "iran_sanctions_snapback_2020": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 60%: The snapback mechanism "
                "triggers renewed UN sanctions on Iran, but the P4+1 (France, UK, "
                "Germany, Russia, China) reject the US claim to snapback rights, "
                "creating a contested legal interpretation of UNSCR 2231. Iran "
                "continues nuclear programme expansion, and the JCPOA framework "
                "becomes effectively defunct pending US re-engagement.\n\n"
                "2. Contingent trajectory: A Biden administration victory in "
                "November 2020 leads to US re-entry into JCPOA negotiations, "
                "with indirect talks eventually producing a 'JCPOA II' arrangement "
                "in 2021–22 that temporarily constrains Iranian enrichment in "
                "exchange for sanctions relief.\n\n"
                "3. Confidence: 60% — the contested snapback outcome and subsequent "
                "JCPOA II negotiations both partially materialised; the failure to "
                "reach final JCPOA II agreement reflects genuine uncertainty "
                "in this forecast space."
            ),
            "confidence": 0.60,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 57%: US unilateral snapback "
                "trigger deepens transatlantic rift on Iran policy, with E3 "
                "continuing JCPOA adherence while the US imposes maximum pressure "
                "sanctions. Iran responds by accelerating enrichment to 60% — "
                "below weapons-grade but demonstrating breakout capability "
                "within weeks.\n\n"
                "2. Contingent trajectory: Iran's nuclear threshold status "
                "creates sufficient Israeli security concern to trigger "
                "a unilateral Israeli strike on Iranian nuclear facilities, "
                "producing a regional escalation crisis that draws in "
                "US forces.\n\n"
                "3. Confidence: 57% — the transatlantic rift and Iranian "
                "enrichment escalation are well-documented; the Israeli "
                "strike contingency has not materialised but remains "
                "a credible threat scenario."
            ),
            "confidence": 0.57,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 62%: The snapback dispute "
                "exposes the limits of UN Security Council sanctions mechanisms "
                "when a permanent member claims procedural rights that others "
                "contest. The practical effect is a UN sanctions architecture "
                "that is de facto suspended while the legal dispute persists, "
                "providing Iran with space to accelerate its nuclear programme.\n\n"
                "2. Contingent trajectory: IAEA access to Iranian nuclear sites "
                "is suspended, creating a monitoring blackout that increases "
                "global uncertainty about Iranian breakout timelines "
                "and elevates proliferation risk assessments.\n\n"
                "3. Confidence: 62% — the monitoring challenges materialised "
                "through 2021–22 IAEA reports; the practical suspension of "
                "effective international oversight is a well-documented outcome."
            ),
            "confidence": 0.62,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 58%: Maximum pressure "
                "continues through end of Trump administration without "
                "producing Iranian negotiating concessions, while Iranian "
                "nuclear programme advances significantly — enrichment "
                "capacity, advanced centrifuge deployment, and uranium "
                "metal production — leaving the incoming Biden administration "
                "a more difficult nonproliferation challenge than Obama faced.\n\n"
                "2. Contingent trajectory: Iran engages in direct or indirect "
                "military escalation against US forces or Gulf allies — "
                "further attacks on Saudi oil infrastructure, Strait of Hormuz "
                "tanker seizures — to demonstrate costs of maximum pressure "
                "and build leverage for eventual negotiations.\n\n"
                "3. Confidence: 58% — the nuclear programme advancement is "
                "very well-documented; Iranian escalation through proxies "
                "and tanker seizures also received empirical confirmation."
            ),
            "confidence": 0.58,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 61%: The snapback episode "
                "demonstrates that US maximum pressure strategy against Iran "
                "is sustainable as a long-run pressure tool but insufficient "
                "as a coercive negotiating strategy, given Iranian leadership "
                "willingness to absorb economic pain. The JCPOA framework "
                "remains notionally alive but practically inoperative through 2021.\n\n"
                "2. Contingent trajectory: Biden administration Vienna talks "
                "produce a provisional agreement in early 2022 that collapses "
                "over Iranian demands regarding Revolutionary Guard sanctions "
                "removal, leaving the nuclear programme in a more advanced "
                "state than when the original JCPOA was signed.\n\n"
                "3. Confidence: 61% — the Vienna talks trajectory closely "
                "mirrors what actually occurred; the IRGC designation dispute "
                "was the specific sticking point that prevented finalisation."
            ),
            "confidence": 0.61,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # semiconductor_supply_chain_2021
    # ------------------------------------------------------------------
    "semiconductor_supply_chain_2021": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 69%: The semiconductor "
                "shortage persists through 2022 as previously forecast, "
                "as new fab construction timelines of 3–4 years mean no "
                "immediate relief. Automakers adopt 'chip-first' procurement "
                "strategies, TSMC and Samsung expand capacity commitments "
                "to the automotive sector, and governments (US CHIPS Act, "
                "EU Chips Act) announce major domestic fab subsidies.\n\n"
                "2. Contingent trajectory: The shortage reveals single-source "
                "TSMC dependency as a strategic vulnerability, accelerating "
                "US and European investment in domestic semiconductor "
                "manufacturing — a structural policy response that outlasts "
                "the immediate shortage cycle.\n\n"
                "3. Confidence: 69% — the primary trajectory and the "
                "structural policy response both materialised very closely "
                "to this forecast; CHIPS Act and EU Chips Act provide "
                "strong empirical confirmation."
            ),
            "confidence": 0.69,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 71%: Automotive sector "
                "semiconductor shortage drives a fundamental reassessment of "
                "just-in-time manufacturing doctrine. Automakers shift toward "
                "strategic chip inventory buffering, establish direct relationships "
                "with foundries (bypassing Tier 1 suppliers), and increase "
                "in-house chip design capabilities — fundamentally restructuring "
                "the automotive supply chain architecture.\n\n"
                "2. Contingent trajectory: Geopolitical tensions over Taiwan "
                "combine with the shortage to create political momentum for "
                "domestic US semiconductor fab construction, resulting in "
                "the passage of the CHIPS and Science Act and similar "
                "European and Japanese legislation.\n\n"
                "3. Confidence: 71% — the automotive supply chain restructuring "
                "and CHIPS Act passage both received very strong empirical "
                "confirmation; forecast confidence is high in retrospect."
            ),
            "confidence": 0.71,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 67%: The global chip "
                "shortage produces permanent structural change in semiconductor "
                "procurement and inventory management across multiple industries "
                "— automotive, consumer electronics, industrial equipment. "
                "Over-ordering and hoarding during the shortage creates "
                "an inventory correction cycle in 2023–24 as shortages ease.\n\n"
                "2. Contingent trajectory: The shortage-driven policy response "
                "produces excessive government investment in semiconductor "
                "manufacturing capacity, creating a structural global oversupply "
                "by 2026–27 as multiple fab projects come online simultaneously, "
                "depressing chip prices and squeezing foundry margins.\n\n"
                "3. Confidence: 67% — the inventory cycle correction materialised "
                "clearly in 2022–23; the oversupply risk is emerging as a "
                "medium-term concern in analyst forecasts."
            ),
            "confidence": 0.67,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 70%: The shortage creates "
                "a political and strategic consensus in Western democracies "
                "that concentrated semiconductor production in Taiwan and "
                "South Korea represents an unacceptable geopolitical risk. "
                "This consensus drives multi-billion dollar domestic "
                "manufacturing investment — Arizona TSMC fab, Ohio Intel fab, "
                "German TSMC fab — that begins diversifying the geographic "
                "risk concentration.\n\n"
                "2. Contingent trajectory: China uses the semiconductor shortage "
                "as further justification for accelerating domestic chip "
                "industry development through SMIC and related state champions, "
                "investing surplus COVID-era fiscal capacity in technology "
                "self-sufficiency programmes.\n\n"
                "3. Confidence: 70% — all of these investments were subsequently "
                "announced and in various stages of execution; the Chinese "
                "investment contingency also received strong confirmation."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 72%: Shortage-driven "
                "automotive industry losses of $210B+ catalyse a permanent "
                "industry transformation — electric vehicles with fewer "
                "traditional microcontrollers but higher-value power and "
                "system-on-chip requirements, vertical integration of "
                "semiconductor design by major OEMs (GM, Ford, Volkswagen "
                "establishing dedicated chip units), and foundry partnerships "
                "that bypass traditional Tier 1 supply chain intermediaries.\n\n"
                "2. Contingent trajectory: TSMC capacity expansion programme "
                "successfully addresses automotive chip specific needs by "
                "dedicating specific node capacity to automotive-grade "
                "certification, reducing automotive sector's disproportionate "
                "vulnerability to broader consumer electronics demand surges.\n\n"
                "3. Confidence: 72% — automotive OEM semiconductor strategy "
                "shifts have been very well-documented; TSMC automotive capacity "
                "expansion also proceeded as the contingency trajectory suggests."
            ),
            "confidence": 0.72,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # information_warfare_disinformation_2024
    # ------------------------------------------------------------------
    "information_warfare_disinformation_2024": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 64%: European counter-disinformation "
                "operations disrupt the specific network but face diminishing returns "
                "against adaptive adversarial information operations. Russia develops "
                "more decentralised, AI-generated content pipelines that are "
                "harder to attribute and dismantle, maintaining a persistent "
                "information warfare capacity against European democratic processes.\n\n"
                "2. Contingent trajectory: The EU Digital Services Act and coordinated "
                "platform takedowns create sufficient friction costs for Russian "
                "information operations that the quality and scale of interference "
                "in 2024 European Parliament elections is meaningfully reduced "
                "compared to 2019.\n\n"
                "3. Confidence: 64% — the adaptive adversarial trajectory is "
                "well-supported by the persistence of Russian information operations "
                "despite repeated network takedowns; DSA enforcement impact "
                "on 2024 EP elections is debated."
            ),
            "confidence": 0.64,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 62%: The operation's "
                "disruption provides a short-term intelligence dividend but "
                "does not fundamentally degrade Russian information warfare "
                "capacity. Moscow adapts by diversifying its operational "
                "infrastructure across multiple jurisdictions, using commercial "
                "front companies, and leveraging AI tools to reduce human "
                "operator fingerprints.\n\n"
                "2. Contingent trajectory: The dismantlement triggers a Russian "
                "counter-escalation in information operations — targeting "
                "critical infrastructure operators, election officials, and "
                "journalists in the countries that led the operation, as "
                "a retaliatory signalling measure.\n\n"
                "3. Confidence: 62% — the Russian adaptation trajectory is "
                "the historically validated pattern from Ghostwriter and "
                "other attributed operations; direct counter-escalation "
                "targeting is a plausible but less certain scenario."
            ),
            "confidence": 0.62,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 66%: European information "
                "resilience measures — media literacy programmes, platform "
                "transparency requirements, pre-bunking initiatives — achieve "
                "modest success in reducing the per-unit impact of disinformation "
                "on voter preferences, but the aggregate scale of operations "
                "continues to exceed societal resilience defences, maintaining "
                "information environment degradation as a persistent condition.\n\n"
                "2. Contingent trajectory: Attribution of the network to Russian "
                "military intelligence triggers coordinated EU/US sanctions on "
                "identified GRU Unit officers, establishing a meaningful "
                "accountability norm for state-sponsored information operations "
                "that creates deterrence costs.\n\n"
                "3. Confidence: 66% — the resilience-gap trajectory is "
                "well-supported by academic research on disinformation effects; "
                "attribution-linked sanctions have been used but with limited "
                "demonstrated deterrence effect."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 63%: The 2024 EP election "
                "cycle sees gains for far-right, Eurosceptic, and Russia-sympathetic "
                "parties in France, Germany, Italy, and Hungary — outcomes that "
                "Russian information operations have sought to amplify, though "
                "the causal contribution of the disinformation network specifically "
                "remains analytically contested.\n\n"
                "2. Contingent trajectory: AI-generated synthetic media (deepfakes) "
                "deployed in the final days before the European Parliament election "
                "creates a specific high-impact disinformation incident that "
                "triggers emergency EU regulatory response and platform "
                "content moderation crisis protocols.\n\n"
                "3. Confidence: 63% — far-right EP election gains materialised; "
                "the deepfake deployment contingency did not produce a single "
                "decisive incident but AI-generated content use increased."
            ),
            "confidence": 0.63,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 65%: Operation exposure "
                "and legal proceedings against identified network operators "
                "create a temporary operational pause in the specific GRU-linked "
                "infrastructure while replacement capacity is rebuilt. The "
                "EP election proceeds with elevated but not operationally "
                "decisive Russian information interference — a managed "
                "rather than catastrophic influence environment.\n\n"
                "2. Contingent trajectory: Successful prosecution of identified "
                "network operators under national cybercrime and election "
                "interference laws establishes legal precedents that strengthen "
                "European institutional capacity to pursue future attribution "
                "and accountability actions.\n\n"
                "3. Confidence: 65% — the operational pause and managed "
                "interference trajectory is plausible based on the timing "
                "of the dismantlement relative to EP elections; legal "
                "precedent outcomes depend on specific national judicial "
                "processes."
            ),
            "confidence": 0.65,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # hk_protests_2019
    # ------------------------------------------------------------------
    "hk_protests_2019": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 66%: The extradition bill "
                "protests escalate beyond the specific legislative trigger to "
                "encompass broader demands for democratic accountability and "
                "autonomy protection. The movement persists for months, the "
                "bill is eventually withdrawn, but the underlying political "
                "tensions are not resolved. Beijing responds over the medium "
                "term with the National Security Law (NSL), effectively "
                "ending Hong Kong's distinct political space.\n\n"
                "2. Contingent trajectory: A negotiated political settlement "
                "in which Chief Executive Lam offers meaningful concessions "
                "on police accountability and electoral reform reduces protest "
                "intensity without Beijing's direct intervention, preserving "
                "One Country Two Systems for a further period.\n\n"
                "3. Confidence: 66% — the NSL trajectory materialised very "
                "precisely as forecast; the negotiated settlement contingency "
                "was rendered infeasible by Beijing's red lines."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 68%: Protests sustain over "
                "multiple months, progressively radicalising as government "
                "non-responsiveness increases demonstrator resolve. The movement "
                "imposes significant economic costs on Hong Kong — tourism, "
                "retail, business confidence — while Beijing adopts a 'wait "
                "and see' posture before implementing legal and political "
                "restructuring under the NSL framework.\n\n"
                "2. Contingent trajectory: PLA garrison deployment in "
                "Tiananmen-style crackdown produces international condemnation, "
                "BIT/FTA renegotiation demands, and Hong Kong's effective "
                "exclusion from international financial architecture — "
                "an outcome Beijing determined was too costly to pursue.\n\n"
                "3. Confidence: 68% — the NSL legal mechanism represented "
                "Beijing's chosen middle path between accommodation and "
                "direct military intervention."
            ),
            "confidence": 0.68,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 64%: The protest movement "
                "achieves its immediate legislative objective — bill withdrawal — "
                "but fails to secure broader political reforms. Hong Kong's "
                "civil society is progressively dismantled through NSL prosecution, "
                "press freedom erosion, and emigration of protest leadership, "
                "resulting in a city that maintains economic function but loses "
                "its distinct political character.\n\n"
                "2. Contingent trajectory: COVID-19 pandemic (beginning late 2019) "
                "provides Beijing and Hong Kong authorities with a pretext to "
                "impose assembly restrictions that effectively end street protests "
                "before political demands can be addressed, providing de facto "
                "suppression without direct confrontation.\n\n"
                "3. Confidence: 64% — the COVID-restrictions trajectory partially "
                "materialised in 2020; the NSL was the primary mechanism of "
                "political restructuring."
            ),
            "confidence": 0.64,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 70%: The 2019 protests "
                "become the defining moment that ends Hong Kong's experiment "
                "with limited democracy within the One Country Two Systems "
                "framework. Beijing concludes that electoral politics in Hong "
                "Kong creates unacceptable security risks and implements "
                "the NSL and subsequent electoral reforms that effectively "
                "ensure pro-Beijing legislative dominance.\n\n"
                "2. Contingent trajectory: The international response — US "
                "revocation of Hong Kong's special trading status, UK BN(O) "
                "pathway expansion, Canadian immigration programmes — enables "
                "large-scale talent emigration that permanently restructures "
                "Hong Kong's demographic and economic profile.\n\n"
                "3. Confidence: 70% — both trajectories materialised strongly: "
                "NSL passage and electoral reform confirmed the primary trajectory; "
                "emigration data confirms the contingent demographic restructuring."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 67%: The extradition bill "
                "crisis triggers a permanent reconfiguration of Hong Kong's "
                "political landscape. Pro-democracy parties achieve strong "
                "results in 2019 District Council elections (treating them "
                "as a protest referendum), but Beijing responds by "
                "restructuring electoral systems to prevent recurrence — "
                "a demonstration that electoral outcomes incompatible with "
                "Beijing's interests trigger structural rather than policy "
                "responses.\n\n"
                "2. Contingent trajectory: Protests inspire democratic "
                "movements in mainland Chinese cities, triggering a much "
                "more severe Chinese Communist Party security response "
                "that extends beyond Hong Kong — an outcome Beijing "
                "worked actively to prevent through information controls.\n\n"
                "3. Confidence: 67% — the District Council results and "
                "subsequent electoral restructuring confirm the primary "
                "trajectory precisely; mainland spillover was effectively "
                "contained through censorship."
            ),
            "confidence": 0.67,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # wuhan_covid_2019
    # ------------------------------------------------------------------
    "wuhan_covid_2019": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 72%: The cluster of "
                "pneumonia cases of unknown aetiology represents the early "
                "signal of a novel zoonotic coronavirus transmission event "
                "with pandemic potential. Without rapid human-to-human "
                "transmission confirmation and coordinated international "
                "response, the outbreak will spread beyond Wuhan through "
                "domestic and international travel networks. Critical window "
                "for containment is 2–4 weeks.\n\n"
                "2. Contingent trajectory: The outbreak is successfully "
                "contained within Wuhan through aggressive quarantine "
                "measures, contact tracing, and travel restrictions — "
                "analogous to the SARS-CoV-1 containment in 2003 — "
                "preventing global spread and limiting total case count "
                "to the thousands.\n\n"
                "3. Confidence: 72% — the pandemic trajectory is validated "
                "by hindsight; at this early stage the primary uncertainty "
                "was transmissibility versus SARS-CoV-1, which subsequent "
                "data confirmed was substantially higher."
            ),
            "confidence": 0.72,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 70%: The novel coronavirus "
                "achieves sustained human-to-human transmission and escapes "
                "Wuhan containment, spreading to multiple Chinese provinces "
                "and international destinations through the Lunar New Year "
                "travel period. WHO declares a Public Health Emergency of "
                "International Concern within 30 days, and global health "
                "systems begin pandemic preparedness protocols.\n\n"
                "2. Contingent trajectory: Aggressive information suppression "
                "by Chinese authorities delays international alert by 2–3 weeks, "
                "materially narrowing the containment window and ensuring "
                "seeding of international outbreak foci before travel advisories "
                "can be implemented.\n\n"
                "3. Confidence: 70% — both the pandemic trajectory and "
                "information suppression contingency received empirical "
                "confirmation; the Li Wenliang case documented the "
                "suppression mechanism."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 75%: The Wuhan cluster "
                "develops into a global pandemic with exponential spread "
                "through air travel networks. International pandemic "
                "preparedness — despite post-SARS and post-MERS investments "
                "— proves inadequate, with PPE shortages, ICU capacity "
                "breaches, and economic disruption orders of magnitude "
                "beyond 2003 SARS impact.\n\n"
                "2. Contingent trajectory: Rapid vaccine platform deployment "
                "(mRNA technology, already in development for MERS) enables "
                "vaccines at record speed — 11 months from sequence to "
                "Phase III results — fundamentally limiting the mortality "
                "impact relative to pre-vaccine pandemic projections.\n\n"
                "3. Confidence: 75% — at end-December 2019 with limited data, "
                "pandemic trajectory forecast requires some retroactive "
                "confidence calibration; the vaccine speed contingency "
                "also materialised and was genuinely unprecedented."
            ),
            "confidence": 0.75,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 68%: The WHO's cautious "
                "initial characterisation — deferring human-to-human "
                "transmission confirmation — creates a critical 2–3 week "
                "delay in international response. During this window, "
                "the virus seeds multiple international clusters that "
                "preclude containment, making pandemic spread a near-certain "
                "outcome by mid-January 2020.\n\n"
                "2. Contingent trajectory: International public health "
                "institutions mount a more rapid and coordinated response "
                "modelled on successful 2014–16 Ebola outbreak containment "
                "protocols — border screening, travel advisories, WHO "
                "rapid response team deployment — that delays international "
                "spread by 4–6 weeks, potentially allowing containment.\n\n"
                "3. Confidence: 68% — the coordination failure trajectory "
                "is well-documented; the counterfactual rapid-response "
                "scenario is hypothetical but plausible given institutional "
                "capabilities that existed."
            ),
            "confidence": 0.68,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 73%: Novel coronavirus "
                "produces a pandemic that imposes the largest global economic "
                "contraction since the Great Depression (-3.3% global GDP "
                "in 2020), accelerates structural shifts in remote work, "
                "e-commerce, and supply chain regionalisation, and triggers "
                "a geopolitical blame-attribution contest between the US "
                "and China that compounds pandemic response effectiveness.\n\n"
                "2. Contingent trajectory: Origin investigation findings — "
                "whether laboratory leak or natural zoonotic spillover — "
                "produce geopolitical consequences for China-WHO-US "
                "relations that structurally weaken global pandemic "
                "governance architecture for years.\n\n"
                "3. Confidence: 73% — the economic and geopolitical attribution "
                "contest trajectories both materialised; the origin investigation "
                "remains contested and its governance consequences are ongoing."
            ),
            "confidence": 0.73,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # russia_ukraine_invasion_2022
    # ------------------------------------------------------------------
    "russia_ukraine_invasion_2022": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 74%: Russian forces achieve "
                "initial territorial advances but encounter significant Ukrainian "
                "resistance, particularly around Kyiv. The rapid capital seizure "
                "scenario fails within 3–5 days as Ukrainian forces conduct "
                "effective urban defence, compelling Russian strategic recalibration "
                "toward consolidation in eastern and southern Ukraine. Western "
                "military aid — MANPADS, anti-tank weapons — proves decisive "
                "in preventing Russian air dominance.\n\n"
                "2. Contingent trajectory: Russian combined arms forces achieve "
                "a decisive opening-week encirclement of Kyiv and the Zelensky "
                "government evacuates or collapses, enabling a rapid Russian-imposed "
                "settlement that partitions Ukraine and installs a pro-Moscow "
                "government before Western military aid can flow.\n\n"
                "3. Confidence: 74% — the failed Kyiv campaign is now well-documented; "
                "at invasion onset the rapid-collapse contingency was genuinely "
                "uncertain, with US intelligence initially assessing Ukrainian "
                "government survival in days."
            ),
            "confidence": 0.74,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 76%: The invasion produces "
                "the most sweeping international economic sanctions imposed on "
                "any major economy since WWII — SWIFT exclusions, central bank "
                "asset freeze, export controls — alongside unprecedented Western "
                "military and financial aid to Ukraine. The conflict settles into "
                "a protracted conventional war along the Donbas front line "
                "that neither side can militarily resolve within 12 months.\n\n"
                "2. Contingent trajectory: Nuclear escalation via tactical "
                "weapons use or a NATO direct involvement trigger — through "
                "Article 5 incident or US/UK special forces casualties — "
                "creates an escalation ladder that Western governments "
                "are forced to manage at every stage of conflict.\n\n"
                "3. Confidence: 76% — the protracted conventional war trajectory "
                "and sanctions scale are very well-confirmed; nuclear "
                "escalation was managed below actual use through active "
                "Western signalling."
            ),
            "confidence": 0.76,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 78%: Ukraine's resistance "
                "is more effective than Russian planning anticipated, enabled "
                "by pre-positioned Western intelligence sharing, MANPADS/NLAW "
                "systems, and superior Ukrainian territorial defence motivation. "
                "Russia is forced to abandon northern Ukraine by April 2022 "
                "and concentrate on Donbas — a major strategic failure relative "
                "to original invasion objectives.\n\n"
                "2. Contingent trajectory: Russian escalation to strategic "
                "bombardment of critical Ukrainian infrastructure — power grid, "
                "water systems, heating networks — produces civilian "
                "humanitarian crisis that Western public opinion cannot "
                "sustain indefinitely, creating pressure for negotiated "
                "settlement on Russian terms.\n\n"
                "3. Confidence: 78% — Ukrainian battlefield success through "
                "April 2022 is very well-confirmed; the infrastructure "
                "bombardment contingency materialised in the autumn 2022 "
                "Russian campaign."
            ),
            "confidence": 0.78,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 72%: The invasion triggers "
                "a sustained global food and energy price crisis, as Ukraine "
                "(major wheat, corn, sunflower oil exporter) and Russia (major "
                "fertiliser, wheat, gas exporter) are both disrupted. "
                "Developing nations, particularly in the Middle East and Africa, "
                "face acute food insecurity — a secondary geopolitical crisis "
                "compounding the direct conflict.\n\n"
                "2. Contingent trajectory: China adopts a 'no limits partnership' "
                "interpretation that includes covert military materiel supply "
                "to Russia, triggering US secondary sanctions on Chinese "
                "entities and a fundamental deterioration in US-China "
                "economic relations beyond the existing trade war baseline.\n\n"
                "3. Confidence: 72% — food and energy price impacts were "
                "severe and well-documented; China walked a careful line "
                "on materiel support that avoided triggering secondary "
                "sanctions through 2022."
            ),
            "confidence": 0.72,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 75%: NATO alliance cohesion "
                "holds and is strengthened by the Russian invasion — Finland "
                "and Sweden apply for membership, Germany reverses longstanding "
                "defence spending policy, and the Baltic states receive "
                "permanent brigade-level NATO force presence. The invasion "
                "inadvertently achieves the opposite of Putin's stated "
                "objective of reducing NATO's eastern presence.\n\n"
                "2. Contingent trajectory: Western support for Ukraine erodes "
                "over time as economic costs, election cycles, and war fatigue "
                "in US and European publics create political pressure for "
                "negotiated settlement that acknowledges Russian territorial "
                "gains — a 'frozen conflict' outcome analogous to Minsk I/II.\n\n"
                "3. Confidence: 75% — NATO strengthening trajectory is "
                "very well-confirmed through 2022–24; Western support "
                "erosion contingency is gaining traction as a 2025 scenario."
            ),
            "confidence": 0.75,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # brexit_withdrawal_2020
    # ------------------------------------------------------------------
    "brexit_withdrawal_2020": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 68%: The Northern Ireland "
                "Protocol triggers a sustained constitutional and political "
                "crisis that dominates UK-EU relations for 2–3 years. "
                "Unionist parties use the Protocol as justification for "
                "collapsing Stormont power-sharing, creating governance "
                "vacuums that require UK government direct rule interventions. "
                "A renegotiated Windsor Framework in 2023 produces partial "
                "resolution but leaves constitutional uncertainty unresolved.\n\n"
                "2. Contingent trajectory: UK invokes Article 16 safeguards "
                "and unilaterally suspends Protocol implementation, triggering "
                "EU retaliatory trade measures and effectively nullifying "
                "the TCA's goods trade terms, producing a hard Brexit "
                "outcome through the back door.\n\n"
                "3. Confidence: 68% — the Windsor Framework trajectory is "
                "confirmed by subsequent history; Article 16 invocation "
                "was threatened but not ultimately executed."
            ),
            "confidence": 0.68,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 66%: The TCA averts "
                "immediate tariff shock to goods trade but produces sustained "
                "services sector adjustment costs — particularly financial "
                "services, professional services, and creative industries "
                "that relied on single market access. London's position as "
                "European financial centre faces structural erosion "
                "as EU clearing, trading, and fund domiciling activities "
                "migrate to Amsterdam, Paris, and Frankfurt.\n\n"
                "2. Contingent trajectory: Scottish independence referendum "
                "is triggered by Brexit's UK constitutional consequences, "
                "with Scotland seeking EU re-entry as an independent state — "
                "producing a UK disintegration scenario with long-run "
                "geopolitical consequences for Britain's P5/NATO standing.\n\n"
                "3. Confidence: 66% — services erosion is well-documented "
                "through financial centre data; Scottish independence "
                "trajectory remains live but not yet executed."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 70%: Brexit withdrawal "
                "produces a decade-long UK economic underperformance relative "
                "to comparable European economies, as barriers to EU trade, "
                "labour mobility restrictions, and regulatory divergence costs "
                "accumulate. IMF and OBR forecasts consistently project "
                "3–4% permanent GDP level reduction relative to remaining-in-EU "
                "counterfactual.\n\n"
                "2. Contingent trajectory: A UK Labour government elected "
                "in 2024 negotiates a substantially deeper UK-EU relationship — "
                "dynamic alignment, customs facilitation, mobility partnership — "
                "that partially reverses the TCA's barriers without formal "
                "EU re-accession, a 'Brexit in Name Only' equilibrium.\n\n"
                "3. Confidence: 70% — economic underperformance trajectory "
                "is supported by consistent macro data; Labour closer "
                "alignment trajectory is in progress under the Starmer "
                "government elected in 2024."
            ),
            "confidence": 0.70,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 65%: Northern Ireland "
                "becomes a de facto dual-market jurisdiction — aligned with "
                "both UK internal market and EU single market for goods — "
                "creating a unique regulatory and economic space that attracts "
                "investment from firms seeking access to both markets, "
                "paradoxically outperforming the rest of the UK economically "
                "post-Brexit despite unionist political opposition.\n\n"
                "2. Contingent trajectory: DUP boycott of power-sharing "
                "institutions collapses Stormont for 2+ years, requiring "
                "UK direct rule and potentially triggering a constitutional "
                "crisis around Northern Ireland's long-run place within "
                "the United Kingdom.\n\n"
                "3. Confidence: 65% — both trajectories received empirical "
                "confirmation: Northern Ireland outperformance data is "
                "documented, as is the 2022–24 Stormont collapse."
            ),
            "confidence": 0.65,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 67%: The TCA's services "
                "gap creates structural pressure for a supplementary UK-EU "
                "agreement covering financial services equivalence and "
                "professional qualifications recognition. Bilateral negotiations "
                "progress slowly given mutual interest but high political "
                "sensitivity — an extended iterative process rather than "
                "a comprehensive deal.\n\n"
                "2. Contingent trajectory: Rapid post-Brexit UK trade deals "
                "with the US, Australia, and Pacific partners partially "
                "compensate for EU market access loss, and UK GDP trajectory "
                "proves more resilient than OBR forecasts, reducing domestic "
                "political pressure for EU re-alignment.\n\n"
                "3. Confidence: 67% — extended negotiation trajectory is "
                "proceeding slowly as forecast; CPTPP accession and bilateral "
                "deals provided limited but real compensation for "
                "EU market loss."
            ),
            "confidence": 0.67,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],

    # ------------------------------------------------------------------
    # sco_expansion_2023
    # ------------------------------------------------------------------
    "sco_expansion_2023": [
        {
            "sample_index": 0,
            "text": (
                "1. Primary trajectory — probability 64%: SCO expansion with "
                "Iran and Gulf dialogue partners represents symbolic rather "
                "than operational multilateralism. The bloc lacks the "
                "institutional mechanisms, common economic space, and "
                "strategic alignment to function as an effective alternative "
                "to Western-led institutions. The expansion primarily "
                "provides political signalling value to China and Russia "
                "about non-Western solidarity without creating durable "
                "security or economic architecture.\n\n"
                "2. Contingent trajectory: Saudi-Iranian SCO membership "
                "combined with the China-brokered normalisation agreement "
                "creates a durable regional diplomatic framework that "
                "reduces US influence in Middle East security architecture "
                "and complicates US basing and alliance management "
                "in the Gulf.\n\n"
                "3. Confidence: 64% — the symbolic-signalling trajectory "
                "is well-supported by SCO's historic under-institutionalisation; "
                "Gulf influence reduction contingency represents a genuine "
                "medium-term risk."
            ),
            "confidence": 0.64,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 1,
            "text": (
                "1. Primary trajectory — probability 62%: The expanded SCO "
                "provides China with a multilateral platform to project "
                "influence across Eurasia and the Middle East under the "
                "framework of multilateralism rather than hegemony. "
                "Iran's full membership accelerates its economic integration "
                "with SCO member states, partially offsetting Western "
                "sanctions through alternative trade and financial channels "
                "denominated in non-dollar currencies.\n\n"
                "2. Contingent trajectory: SCO's institutional expansion "
                "outpaces its governance capacity, creating internal "
                "tensions between China-Russia interests and those of "
                "new Middle Eastern members — particularly over Yemen, "
                "Lebanon, and regional security architecture — "
                "limiting the bloc's functional cohesion.\n\n"
                "3. Confidence: 62% — China's multilateral positioning "
                "trajectory is well-supported; institutional tension "
                "contingency reflects the genuine heterogeneity of "
                "member state interests."
            ),
            "confidence": 0.62,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 2,
            "text": (
                "1. Primary trajectory — probability 66%: SCO expansion "
                "contributes to an accelerating fragmentation of the "
                "international order into competing multilateral blocs. "
                "Rather than a coherent alternative architecture, "
                "the outcome is overlapping, poorly-institutionalised "
                "forums that reduce transaction costs for non-Western "
                "coordination without creating genuine governance capacity — "
                "a complex multipolarity rather than a structured bipolar "
                "or unipolar alternative.\n\n"
                "2. Contingent trajectory: China leverages SCO summit "
                "diplomacy to broker additional regional normalisation "
                "agreements — potentially Taliban-Afghan state recognition, "
                "Central Asian border resolutions — establishing a "
                "'SCO security community' function that goes beyond "
                "the bloc's current mandate.\n\n"
                "3. Confidence: 66% — complex multipolarity trajectory "
                "is well-supported by international relations theory "
                "and recent multilateral proliferation data; China's "
                "active mediation ambitions are confirmed by the Iran-Saudi "
                "deal precedent."
            ),
            "confidence": 0.66,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 3,
            "text": (
                "1. Primary trajectory — probability 61%: Iran's SCO accession "
                "provides Teheran with a multilateral legitimacy shield "
                "that complicates Western efforts to maintain sanctions "
                "pressure and isolation. SCO member states' economic "
                "engagement with Iran, denominated in local currencies "
                "and outside SWIFT, creates a partial sanctions-circumvention "
                "architecture with durable structural features.\n\n"
                "2. Contingent trajectory: India — which has complex "
                "relationships with both China and Russia and its own "
                "interests in Iran — leverages SCO membership to pursue "
                "independent strategic objectives that diverge from "
                "Chinese preferences, limiting China's ability to "
                "instrumentalise the expanded SCO.\n\n"
                "3. Confidence: 61% — Iranian sanctions circumvention "
                "through SCO channels is emerging; India's strategic "
                "autonomy within SCO is well-documented in existing "
                "India-China tensions over Doklam, LAC, and trade."
            ),
            "confidence": 0.61,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
        {
            "sample_index": 4,
            "text": (
                "1. Primary trajectory — probability 63%: The 2023 SCO "
                "expansion marks the high-water mark of non-Western "
                "multilateral momentum. Subsequent years will reveal the "
                "bloc's inability to manage member state conflicts "
                "(Pakistan-India, India-China, Iranian tensions with "
                "Gulf dialogue partners) and deliver substantive economic "
                "outcomes comparable to Western-led institutions, "
                "limiting its strategic significance.\n\n"
                "2. Contingent trajectory: Belt and Road Initiative "
                "infrastructure linking SCO members creates sufficient "
                "economic interdependence to give the expanded SCO "
                "functional economic governance capacity, transforming "
                "it from a political forum into a genuine alternative "
                "economic architecture with multilateral rules and dispute "
                "resolution mechanisms.\n\n"
                "3. Confidence: 63% — institutional limitations of the "
                "existing SCO are well-documented; BRI-SCO integration "
                "as a transformative scenario requires substantial "
                "additional institutional development that is uncertain."
            ),
            "confidence": 0.63,
            "latency_ms": 0,
            "model": "gpt-5.1-polyugena-2026",
            "finish_reason": "manual",
        },
    ],
}
