# EL-DRUIN Baseline Experiments

This directory contains the reproducible experimental framework used in Section 7
of the EL-DRUIN paper for the EL-DRUIN vs GPT-4 baseline comparison.

---

## Quick Start

### 1. Set your OpenAI API Key (required only for GPT-4 baseline)

```bash
export OPENAI_API_KEY="sk-..."
```

> **Never commit your API key.**  The key is read at runtime from the
> environment variable above.  If `OPENAI_API_KEY` is not set, the script
> skips the GPT-4 baseline and runs EL-DRUIN only.

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
pip install openai          # only needed for GPT-4 baseline
```

### 3. Run the full experiment

From the **repository root**:

```bash
python experiments/run_baseline.py
```

This will:
- Load all samples from `experiments/news_samples.jsonl`
- Run the EL-DRUIN evented pipeline on each excerpt (no API key needed)
- Run the GPT-4 baseline N=5 times per excerpt (requires `OPENAI_API_KEY`)
- Save per-sample JSON files under `experiments/results/`

### 4. Generate the comparison table

```bash
python experiments/compute_metrics.py
```

This reads the results and writes:
- `experiments/comparison_table.md` — Markdown table (suitable for copy-paste into the paper)
- `experiments/comparison_table.csv` — CSV version for further analysis

---

## Options

### Run EL-DRUIN only (offline / CI)

```bash
python experiments/run_baseline.py --skip-gpt
```

### Run a subset of samples

```bash
python experiments/run_baseline.py --ids us_china_chips_2023 russia_swift_2022
```

### Use a different model

```bash
export GPT_MODEL=gpt-4-turbo
python experiments/run_baseline.py
```

### Change the number of GPT samples per item

```bash
export GPT_N_SAMPLES=10
python experiments/run_baseline.py
```

---

## Dataset: `news_samples.jsonl`

Each line is a JSON object with the following fields:

| Field     | Type     | Description                                               |
|-----------|----------|-----------------------------------------------------------|
| `id`      | string   | Unique sample identifier                                  |
| `title`   | string   | Article headline                                          |
| `url`     | string   | Public URL of the original article                        |
| `date`    | string   | Publication date (YYYY-MM-DD)                             |
| `source`  | string   | Publisher name (e.g. Reuters, Brookings Institution)      |
| `excerpt` | string   | Short excerpt ≤ ~200 words (no long copyrighted text)     |
| `tags`    | string[] | Thematic tags (e.g. `["export_control", "technology"]`)   |

Only the `excerpt` is used in the analysis.  The `url` field ensures every
sample is traceable to its original public source.

### Covered themes

| Theme                          | Sample IDs                                      |
|--------------------------------|-------------------------------------------------|
| Technology / export control    | `us_china_chips_2023`, `huawei_ban_2019`        |
| Trade war / decoupling         | `us_china_trade_tariffs_2018`                   |
| Financial isolation / SWIFT    | `russia_swift_2022`                             |
| Military coercion / deterrence | `taiwan_military_drills_2022`                   |
| Energy weaponisation           | `russia_ukraine_energy_2022`                    |
| Military alliance              | `nato_eastern_flank_2022`                       |
| Multilateral sanctions         | `iran_sanctions_snapback_2020`                  |
| Supply-chain dependency        | `semiconductor_supply_chain_2021`               |
| Information warfare            | `information_warfare_disinformation_2024`       |

Sources include: Reuters, BBC News, Financial Times, Brookings Institution,
CSIS, NATO, Wall Street Journal — a mix of mainstream media and policy think
tanks as agreed in the experiment design.

---

## Metrics Explained

| Metric                    | EL-DRUIN                                                      | GPT-4 Baseline                                   |
|---------------------------|---------------------------------------------------------------|--------------------------------------------------|
| **Traceability**          | `compute_trace_ref` field links every confidence to the algebraic derivation | No compute trace; confidence is a free-text assertion |
| **Auditability**          | Full pipeline is deterministic; output can be reproduced from the same input | Stochastic; outputs differ across runs           |
| **Stability (σ)**         | σ = 0.000 (deterministic)                                     | σ > 0 across N=5 samples (stochastic LLM)       |
| **Entity invention**      | Guardrail detects and rejects conclusions with invented proper nouns | No enforcement layer                             |
| **CJK leakage**           | Guardrail rejects any output containing CJK characters        | Not applicable                                   |
| **Numeric consistency**   | Probabilities derive from the formula; cannot change arbitrarily | Self-reported; can vary inconsistently           |

---

## Reproducing the Paper Results

The exact results in the paper were generated with:

```bash
export OPENAI_API_KEY="<key used at submission time>"
export GPT_MODEL=gpt-4o
export GPT_N_SAMPLES=5
python experiments/run_baseline.py
python experiments/compute_metrics.py
```

The EL-DRUIN results are fully deterministic and will always reproduce
identically.  The GPT-4 results may differ slightly due to model updates,
but the aggregate statistics (mean confidence, standard deviation, violation
counts) should remain in the same range.
