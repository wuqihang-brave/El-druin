#!/usr/bin/env python3
"""
experiments/run_baseline.py
============================
Reproducible baseline comparison experiment for EL-DRUIN vs GPT-4 / GPT-5.1.

Usage
-----
    export OPENAI_API_KEY="sk-..."
    python experiments/run_baseline.py [--samples experiments/news_samples.jsonl] \
                                        [--output experiments/results/]

For each news sample in news_samples.jsonl the script:
1. Runs the EL-DRUIN evented pipeline (deterministic, no API key required).
2. Runs the GPT baseline N=5 times with an identical analytical prompt.
3. Saves all outputs as JSON under experiments/results/.

The run is designed to be reproducible: the EL-DRUIN output is deterministic
(same input → same output always) while the GPT outputs demonstrate the
variance inherent in stochastic LLM generation.

Environment variables
---------------------
OPENAI_API_KEY   OpenAI API key (required for live GPT baseline only)
GPT_MODEL        Model identifier (default: gpt-4o)
GPT_N_SAMPLES    Number of GPT samples per news item (default: 5)

Manual baseline (no API key required)
--------------------------------------
python experiments/run_baseline.py --inject-manual-gpt
  Injects pre-collected GPT-5.1 (PolyU GenAI, 2026) responses.
  See experiments/gpt_manual_data.py for the raw data and collection protocol.

Do NOT commit your API key.  Set it via the environment variable above.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Allow running from either repo root or experiments/ directory
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_SAMPLES = _REPO_ROOT / "experiments" / "news_samples.jsonl"
_DEFAULT_OUTPUT  = _REPO_ROOT / "experiments" / "results"
_GPT_MODEL       = os.environ.get("GPT_MODEL", "gpt-4o")
_GPT_N_SAMPLES   = int(os.environ.get("GPT_N_SAMPLES", "5"))
_GPT_SYSTEM_PROMPT = (
    "You are a professional geopolitical intelligence analyst. "
    "Provide a structured forecast of the most likely and contingent trajectories "
    "based on the news excerpt provided. "
    "Assign a probability estimate (0–100%) to the primary trajectory. "
    "State your confidence level and how you arrived at it. "
    "Be concise: 3–5 sentences total."
)
_GPT_USER_TEMPLATE = (
    "News excerpt:\n{excerpt}\n\n"
    "Please provide a geopolitical intelligence forecast including:\n"
    "1. Primary trajectory (most likely outcome) with probability estimate\n"
    "2. Contingent/alternative trajectory\n"
    "3. Your confidence level and its basis"
)


# ---------------------------------------------------------------------------
# EL-DRUIN runner
# ---------------------------------------------------------------------------

def run_eldruin(excerpt: str) -> Dict[str, Any]:
    """Run the EL-DRUIN evented pipeline on *excerpt* and return serialisable output."""
    from intelligence.evented_pipeline import run_evented_pipeline

    result = run_evented_pipeline(excerpt, llm_service=None)

    # Collect only the fields needed for the comparison table
    return {
        "events": result.events,
        "active_patterns": result.active_patterns,
        "top_transitions": result.top_transitions,
        "conclusion": result.conclusion,
        "credibility": result.credibility,
        # Compute-trace reference — the key auditability field
        "compute_trace_ref": result.conclusion.get("final", {}).get(
            "compute_trace_ref", "N/A"
        ),
        "confidence": result.conclusion.get("confidence", None),
        "mode": result.conclusion.get("mode", "deterministic_fallback"),
    }


# ---------------------------------------------------------------------------
# GPT-4 baseline runner
# ---------------------------------------------------------------------------

def run_gpt_baseline(
    excerpt: str,
    n_samples: int = _GPT_N_SAMPLES,
    model: str = _GPT_MODEL,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run the GPT-4 baseline *n_samples* times on *excerpt*.

    Returns a list of dicts, each containing:
        - text:       raw LLM output
        - confidence: self-reported confidence extracted from text (if parseable)
        - latency_ms: wall-clock latency in ms
        - model:      model identifier

    Raises RuntimeError if the OpenAI client cannot be initialised.
    """
    try:
        import openai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "openai package not installed.  Run: pip install openai"
        ) from exc

    _key = api_key or os.environ.get("OPENAI_API_KEY")
    if not _key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable not set.  "
            "Export it before running: export OPENAI_API_KEY='sk-...'"
        )

    client = openai.OpenAI(api_key=_key)
    user_message = _GPT_USER_TEMPLATE.format(excerpt=excerpt)
    outputs: List[Dict[str, Any]] = []

    for i in range(n_samples):
        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _GPT_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.7,
                max_tokens=512,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            text = response.choices[0].message.content or ""
            outputs.append({
                "sample_index": i,
                "text": text,
                "confidence": _extract_gpt_confidence(text),
                "latency_ms": latency_ms,
                "model": model,
                "finish_reason": response.choices[0].finish_reason,
            })
        except Exception as exc:  # pylint: disable=broad-except
            latency_ms = int((time.monotonic() - t0) * 1000)
            outputs.append({
                "sample_index": i,
                "text": f"ERROR: {exc}",
                "confidence": None,
                "latency_ms": latency_ms,
                "model": model,
                "finish_reason": "error",
            })
        # Polite rate-limit back-off between samples
        if i < n_samples - 1:
            time.sleep(0.5)

    return outputs


def _extract_gpt_confidence(text: str) -> Optional[float]:
    """Heuristically extract a self-reported probability/confidence from GPT output."""
    import re
    patterns = [
        r"(\d{1,3})\s*(?:percent|%)\s*(?:confidence|probability|likely)",
        r"(?:confidence|probability|likely)(?:\s+(?:of|at|is))?\s*(\d{1,3})\s*%",
        r"(\d{1,3})\s*%",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 <= val <= 100:
                return round(val / 100, 4)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_samples(path: Path) -> List[Dict[str, Any]]:
    samples = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description="EL-DRUIN vs GPT baseline experiment")
    parser.add_argument(
        "--samples", default=str(_DEFAULT_SAMPLES),
        help="Path to news_samples.jsonl"
    )
    parser.add_argument(
        "--output", default=str(_DEFAULT_OUTPUT),
        help="Output directory for result JSON files"
    )
    parser.add_argument(
        "--skip-gpt", action="store_true",
        help="Skip GPT baseline (run EL-DRUIN only; useful for CI / offline testing)"
    )
    parser.add_argument(
        "--inject-manual-gpt", action="store_true",
        help=(
            "Inject manually-collected GPT-5.1 (PolyU GenAI, 2026) baseline results "
            "instead of calling the OpenAI API. Use this when API key is unavailable "
            "but manual collection has been completed."
        )
    )
    parser.add_argument(
        "--ids", nargs="*",
        help="Only process samples with these IDs (default: all)"
    )
    args = parser.parse_args()

    samples_path = Path(args.samples)
    output_dir   = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = load_samples(samples_path)
    if args.ids:
        samples = [s for s in samples if s.get("id") in args.ids]

    # Load manual GPT responses if requested
    manual_gpt_data: Dict[str, Any] = {}
    if args.inject_manual_gpt:
        _experiments_dir = Path(__file__).resolve().parent
        if str(_experiments_dir.parent) not in sys.path:
            sys.path.insert(0, str(_experiments_dir.parent))
        from experiments.gpt_manual_data import GPT_MANUAL_RESPONSES  # type: ignore
        manual_gpt_data = GPT_MANUAL_RESPONSES

    print(f"Processing {len(samples)} sample(s)…")

    for sample in samples:
        sid     = sample["id"]
        excerpt = sample["excerpt"]
        print(f"\n[{sid}] Running EL-DRUIN…", end=" ", flush=True)
        eldruin_result = run_eldruin(excerpt)
        print("done.", flush=True)

        gpt_results: List[Dict[str, Any]] = []
        if args.inject_manual_gpt:
            gpt_results = manual_gpt_data.get(sid, [])
            n = len(gpt_results)
            print(f"[{sid}] GPT-5.1 manual baseline injected (N={n})", flush=True)
        elif not args.skip_gpt:
            print(f"[{sid}] Running GPT baseline (N={_GPT_N_SAMPLES})…", end=" ", flush=True)
            try:
                gpt_results = run_gpt_baseline(excerpt)
                print("done.", flush=True)
            except RuntimeError as exc:
                print(f"SKIPPED ({exc})", flush=True)

        combined = {
            "id":            sid,
            "title":         sample.get("title", ""),
            "url":           sample.get("url", ""),
            "date":          sample.get("date", ""),
            "source":        sample.get("source", ""),
            "tags":          sample.get("tags", []),
            "excerpt":       excerpt,
            "eldruin":       eldruin_result,
            "gpt_baseline":  gpt_results,
        }

        out_path = output_dir / f"{sid}.json"
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(combined, fh, ensure_ascii=False, indent=2)
        print(f"[{sid}] Saved → {out_path}", flush=True)

    print(f"\nAll done.  Results in: {output_dir}")


if __name__ == "__main__":
    main()
