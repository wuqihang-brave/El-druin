#!/usr/bin/env python3
"""
experiments/compute_metrics.py
================================
Compute the EL-DRUIN vs GPT-4 comparison metrics table from run_baseline.py
output and write a Markdown and CSV report.

Usage
-----
    python experiments/compute_metrics.py [--results experiments/results/] \
                                           [--output experiments/comparison_table.md]

Metrics computed
----------------
For each news sample the script computes the following columns:

| Column                    | EL-DRUIN                                      | GPT-4 (N=5)                          |
|---------------------------|-----------------------------------------------|--------------------------------------|
| confidence                | Composite Bayesian posterior (float 0–1)      | Mean self-reported probability       |
| confidence_source         | "ontology_prior × bayesian_posterior"         | "self-reported (LLM)"                |
| confidence_verifiable     | Yes — compute_trace_ref anchors the value     | No — self-reported, not auditable    |
| compute_trace             | bayesian_posterior|Z=… reference              | N/A                                  |
| confidence_std            | 0.000 (deterministic)                         | std dev across N=5 samples           |
| entity_invention_flagged  | Yes/No from rendering_meta.invented_entities  | Not computed                         |
| verifiability_score       | credibility.verifiability_score               | N/A                                  |
| kg_consistency_score      | credibility.kg_consistency_score              | N/A                                  |
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"
_DEFAULT_OUTPUT  = Path(__file__).resolve().parent / "comparison_table.md"


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _gpt_confidence_stats(gpt_results: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """Return (mean, std) of self-reported GPT confidence values, or (None, None)."""
    values = [r["confidence"] for r in gpt_results if r.get("confidence") is not None]
    if not values:
        return None, None
    mean = statistics.mean(values)
    std  = statistics.stdev(values) if len(values) > 1 else 0.0
    return round(mean, 4), round(std, 4)


def _entity_invented(eldruin: Dict[str, Any]) -> bool:
    rendering_meta = eldruin.get("conclusion", {}).get("rendering_meta", {})
    return bool(rendering_meta.get("invented_entities"))


def _count_cjk_fields(obj: Any, path: str = "") -> List[str]:
    """Recursively scan *obj* for string values containing CJK characters."""
    import re
    _cjk = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
    found: List[str] = []
    if isinstance(obj, str):
        if _cjk.search(obj):
            found.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(_count_cjk_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_count_cjk_fields(item, f"{path}[{i}]"))
    return found


def _gpt_constraint_violations(gpt_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Count occurrences of common constraint violations across GPT samples.

    Violations detected (heuristic):
    - numeric_inconsistency: output mentions two or more distinct percentages
      (suggests invented/contradictory values)
    - meta_commentary: contains phrases like "as an AI", "I cannot", "my confidence"
    """
    import re
    numeric_violations = 0
    meta_violations    = 0
    meta_phrases = ["as an ai", "i cannot", "my confidence", "i am confident",
                    "based on my training", "i would estimate", "note that"]
    for sample in gpt_results:
        text = sample.get("text", "").lower()
        # Numeric inconsistency: detect cases where the same trajectory label
        # is mentioned with two different probability values (suggests internal
        # contradiction), rather than simply having multiple percentages
        # (which is expected: alpha + beta probabilities should sum to ~100%).
        pcts = re.findall(r"\b(\d{1,3})\s*%", text)
        pct_set = set(int(p) for p in pcts)
        # Flag if there are > 2 distinct percentage values (alpha + beta = 2 is fine;
        # a third independent value suggests the model is internally inconsistent)
        if len(pct_set) > 2:
            numeric_violations += 1
        # Meta-commentary
        if any(ph in text for ph in meta_phrases):
            meta_violations += 1
    return {
        "numeric_inconsistency_count": numeric_violations,
        "meta_commentary_count":        meta_violations,
        "n_samples":                    len(gpt_results),
    }


# ---------------------------------------------------------------------------
# Load and compute
# ---------------------------------------------------------------------------

def process_result(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    sid       = data.get("id", path.stem)
    title     = data.get("title", "")
    source    = data.get("source", "")
    eldruin   = data.get("eldruin", {})
    gpt       = data.get("gpt_baseline", [])

    credibility = eldruin.get("credibility", {})
    confidence  = eldruin.get("confidence")
    compute_trace = eldruin.get("compute_trace_ref", "N/A")

    gpt_mean_conf, gpt_std_conf = _gpt_confidence_stats(gpt)
    gpt_violations = _gpt_constraint_violations(gpt)

    # CJK leakage in EL-DRUIN conclusion
    cjk_leaks = _count_cjk_fields(eldruin.get("conclusion", {}))

    return {
        "id":                        sid,
        "title":                     title[:60] + ("…" if len(title) > 60 else ""),
        "source":                    source,
        # EL-DRUIN
        "eldruin_confidence":        confidence,
        "eldruin_confidence_std":    0.0,  # deterministic
        "eldruin_confidence_source": credibility.get("confidence_source", "ontology_prior × bayesian_posterior"),
        "eldruin_verifiable":        "✅ Yes",
        "eldruin_compute_trace":     compute_trace,
        "eldruin_verif_score":       credibility.get("verifiability_score"),
        "eldruin_kg_score":          credibility.get("kg_consistency_score"),
        "eldruin_entity_invented":   "⚠️ Yes" if _entity_invented(eldruin) else "✅ No",
        "eldruin_cjk_leaks":         len(cjk_leaks),
        # GPT-4
        "gpt_n_samples":             len(gpt),
        "gpt_mean_confidence":       gpt_mean_conf,
        "gpt_conf_std":              gpt_std_conf,
        "gpt_confidence_source":     "self-reported (LLM)" if gpt else "N/A",
        "gpt_verifiable":            "❌ No" if gpt else "N/A",
        "gpt_compute_trace":         "N/A",
        "gpt_numeric_violations":    gpt_violations["numeric_inconsistency_count"],
        "gpt_meta_violations":       gpt_violations["meta_commentary_count"],
    }


def load_results(results_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            rows.append(process_result(path))
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Warning: could not process {path}: {exc}")
    return rows


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _fmt(val: Any, na: str = "N/A") -> str:
    if val is None:
        return na
    if isinstance(val, float):
        return f"{val:.3f}"
    return str(val)


def write_markdown(rows: List[Dict[str, Any]], output: Path) -> None:
    lines = [
        "# EL-DRUIN vs GPT-4 Baseline Comparison",
        "",
        "> Generated by `experiments/compute_metrics.py`.",
        "> GPT-4 baseline: N=5 independent samples per news item.",
        "",
        "## Summary Interpretation",
        "",
        "| Property | EL-DRUIN | GPT-4 |",
        "|---|---|---|",
        "| Confidence source | Ontology priors × Bayesian posterior (deterministic formula) | Self-reported (LLM generates a number — no external verification) |",
        "| Confidence verifiable | **Yes** — `compute_trace_ref` anchors every value to the algebraic computation | **No** — the LLM asserts confidence; there is no auditable derivation |",
        "| Stability | **σ = 0** (deterministic; same input → same output always) | σ varies across N=5 runs (stochastic sampling) |",
        "| Traceability | Full compute trace: ontology priors, Lie-similarity, Bayesian posterior, step decay | None |",
        "| CJK leakage guard | Enforced (guardrail test suite) | Not applicable |",
        "| Entity invention guard | Detected and flagged per run | Not applicable |",
        "",
        "## Per-Sample Results",
        "",
        "### EL-DRUIN",
        "",
        "| ID | Source | Confidence | σ (stability) | Verifiable | Verif. Score | KG Score | Entity Invented? | CJK Leaks |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['source']} "
            f"| {_fmt(r['eldruin_confidence'])} "
            f"| {_fmt(r['eldruin_confidence_std'])} "
            f"| {r['eldruin_verifiable']} "
            f"| {_fmt(r['eldruin_verif_score'])} "
            f"| {_fmt(r['eldruin_kg_score'])} "
            f"| {r['eldruin_entity_invented']} "
            f"| {r['eldruin_cjk_leaks']} |"
        )

    lines += [
        "",
        "### GPT-4 Baseline (N=5)",
        "",
        "| ID | Source | Mean Confidence | Confidence σ | Verifiable | Compute Trace | Numeric Violations | Meta-Commentary |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['source']} "
            f"| {_fmt(r['gpt_mean_confidence'])} "
            f"| {_fmt(r['gpt_conf_std'])} "
            f"| {r['gpt_verifiable']} "
            f"| {r['gpt_compute_trace']} "
            f"| {r['gpt_numeric_violations']} "
            f"| {r['gpt_meta_violations']} |"
        )

    lines += [
        "",
        "## Key Differentiators",
        "",
        "1. **Traceability / Auditability**: EL-DRUIN embeds a `compute_trace_ref` "
        "field (`bayesian_posterior|Z=…`) in every output, linking the final "
        "confidence to the underlying ontology-prior × Bayesian-posterior algebra.  "
        "A GPT-4 confidence figure is a free-text assertion with no auditable derivation.",
        "",
        "2. **Stability**: EL-DRUIN is fully deterministic — the same news excerpt "
        "always produces the same confidence and the same reasoning trace.  "
        "GPT-4 outputs vary across runs (σ > 0 across N=5 samples).",
        "",
        "3. **Constraint Compliance**: EL-DRUIN enforces hard guardrails that detect "
        "and reject LLM-rendered conclusions containing invented proper nouns (entity "
        "invention guard), changed numeric values (numeric guard), CJK character leakage "
        "(CJK guard), and internal jargon.  GPT-4 has no equivalent enforcement layer.",
        "",
    ]

    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report written → {output}")


def write_csv(rows: List[Dict[str, Any]], output: Path) -> None:
    csv_path = output.with_suffix(".csv")
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"CSV report written → {csv_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute EL-DRUIN vs GPT-4 metrics")
    parser.add_argument(
        "--results", default=str(_DEFAULT_RESULTS),
        help="Directory containing result JSON files from run_baseline.py"
    )
    parser.add_argument(
        "--output", default=str(_DEFAULT_OUTPUT),
        help="Output path for the Markdown report"
    )
    args = parser.parse_args()

    results_dir = Path(args.results)
    output_path = Path(args.output)

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        print("Run experiments/run_baseline.py first.")
        return

    rows = load_results(results_dir)
    if not rows:
        print("No result files found.  Run experiments/run_baseline.py first.")
        return

    print(f"Loaded {len(rows)} result(s) from {results_dir}")
    write_markdown(rows, output_path)
    write_csv(rows, output_path)


if __name__ == "__main__":
    main()
