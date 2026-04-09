# EL-DRUIN 🛡️

**Ontological Trajectory Forecasting via Finite Semigroup Iteration and Lie Algebra Approximation in Geopolitical Knowledge Graphs**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg)](https://streamlit.io/)

> Paper: *Ontological Trajectory Forecasting via Finite Semigroup Iteration and Lie Algebra Approximation in Geopolitical Knowledge Graphs*  
> Author: Qihang Wu — The Hong Kong Polytechnic University  
> Repository: https://github.com/wuqihang-brave/El-druin

---
```mermaid
graph TD
    classDef input fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef processing fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef inference fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef integration fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
    classDef output fill:#ffebee,stroke:#b71c1c,stroke-width:2px;

    subgraph S1 [1. Text Processing & Event Extraction]
        A[Text Input] --> B[Events Extraction<br/>T2/T1 + Evidence Anchors]
    end
    class S1 input;

    subgraph S2 [2. Mechanism & Pattern Mapping]
        B --> C[Mechanism Labels]
        C --> D[Cartesian Pattern Mapping]
    end
    class S2 processing;

    subgraph S3 [3. Transition Candidates]
        D --> E[Transition Generation]
    end
    class S3 processing;

    subgraph S4 [4. Dual Inference Engine]
        E --> F1[Bayesian: P_Bayes C]
        E --> F2[Lie: Nonlinear Activation 8D]
    end
    class S4 inference;

    subgraph S5 [5. Integration & Diagnostics]
        F1 --> G[Consistency Alignment]
        F2 --> G
        G --> H[Final Confidence]
        H --> I[Divergence/Emergence Diagnostics]
    end
    class S5 integration;

    subgraph S6 [6. Rendering & Output]
        I --> J[Path Rendering]
        J --> K[Strip/Escape Keys]
        K --> L((Final User Output))
    end
    class S6 output;
---
## ⚡ 60-Second Overview

EL-DRUIN is an ontology-driven geopolitical intelligence platform that replaces LLM-generated confidence scores with **provably traceable, algebraically derived** confidence values.

| Property | EL-DRUIN | GPT-4 Baseline |
|---|---|---|
| Confidence source | Ontology priors × Bayesian posterior (deterministic formula) | Self-reported by LLM |
| Verifiable? | **Yes** — every value anchored to a `compute_trace_ref` | **No** — free-text assertion |
| Stability | σ = 0 (deterministic; same input → same output) | σ > 0 (stochastic) |
| Traceability | Full compute trace (ontology → Lie algebra → Bayesian) | None |
| Entity invention guard | Enforced — hallucinated proper nouns trigger deterministic fallback | Not implemented |

**Why it matters for intelligence analysis:** when an analyst reads "73% probability", they need to know *where that number came from*. EL-DRUIN's confidence values are products of explicit algebraic operations over a formal ontology, not stochastic LLM outputs.

---

## 🎯 Key Features

- [x] **Finite Semigroup Forward Simulation** — 18 named dynamic patterns with a declarative composition table; forward iteration converges to fixed-point attractors
- [x] **8D Lie Algebra State Vectors** — each pattern embedded as a vector; Lie-bracket similarity scores transition quality
- [x] **Bayesian Posterior with Step Decay** — `w_t = π(A) · π(B) · lie_sim(A,B,C) · λᵗ`; fully auditable formula
- [x] **Compute Trace Reference** — every output includes `compute_trace_ref: "bayesian_posterior|Z=…"` linking result to algebra
- [x] **CJK Leakage Guard** — automated test suite prevents any CJK characters leaking into English user-facing outputs
- [x] **Invented Entity Guard** — LLM rendering pass rejects outputs containing proper nouns not present in the input text
- [x] **Numeric Consistency Guard** — probability values cannot change between deterministic computation and LLM rendering
- [x] **Knowledge Graph Layer** — KuzuDB-backed entity and relationship storage with fuzzy deduplication
- [x] **Five-Tab Streamlit UI** — Conclusion / Events / Pattern Activation / Probability Tree / Object Explorer
- [ ] Learned pattern vectors (currently expert-annotated)
- [ ] Historical backtesting against labelled outcome data
- [ ] Extended composition table coverage (currently ~4% of all pattern pairs)

---

## 🚀 Quickstart

### Prerequisites

- Python 3.9+
- Git
- Docker & Docker Compose (recommended for full stack)

### Option A: Hosted Demo (no setup required)

| Service | URL |
|---|---|
| **Streamlit frontend demo** | https://eldruin-intelligence.streamlit.app |
| **FastAPI docs (live API)** | https://el-druin-production.up.railway.app/docs |

### Option B: Local — Streamlit frontend

```bash
git clone https://github.com/wuqihang-brave/El-druin.git
cd El-druin
python -m venv venv && source venv/bin/activate
pip install -r frontend/requirements.txt
cp .env.example .env   # add API keys if desired
streamlit run frontend/app.py
# Opens at http://localhost:8501
```

### Option C: Local — FastAPI backend

```bash
# (inside the same venv, or a fresh one)
pip install -r backend/requirements.txt
cp .env.example .env   # set LLM_PROVIDER, OPENAI_API_KEY, etc.
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
# API docs at http://localhost:8001/docs
```

### Option D: Docker (full stack)

```bash
git clone https://github.com/wuqihang-brave/El-druin.git
cd El-druin
cp .env.example .env
# Edit .env: add OPENAI_API_KEY and other keys as needed
docker-compose up -d
```

Open:
- **Frontend (Streamlit):** http://localhost:8501
- **Backend API (FastAPI):** http://localhost:8001/docs

Stop:
```bash
docker-compose down
```

### Option E: Pipeline only (no API key)

```bash
cd El-druin
pip install -r backend/requirements.txt
python -c "
import sys; sys.path.insert(0, 'backend')
from intelligence.evented_pipeline import run_evented_pipeline
result = run_evented_pipeline(
    'The US imposed sweeping semiconductor export controls on China, '
    'restricting Nvidia GPU sales and targeting advanced AI chips.'
)
import json
print(json.dumps({
    'confidence': result.conclusion['confidence'],
    'compute_trace_ref': result.conclusion['final']['compute_trace_ref'],
    'primary_attractor': result.top_transitions[0]['to_pattern'] if result.top_transitions else 'N/A',
}, indent=2))
"
```

---

## 🎬 Demo

| Service | Link |
|---|---|
| **Live Streamlit frontend** | https://eldruin-intelligence.streamlit.app |
| **Live FastAPI docs** | https://el-druin-production.up.railway.app/docs |

To run the Streamlit demo locally:

```bash
streamlit run frontend/app.py
```

Then paste any geopolitical news excerpt into the analysis box.
The five tabs display:
1. **Conclusion** — structured alpha/beta trajectory judgement with compute trace
2. **Events** — extracted event types with evidence quotes
3. **Pattern Activation** — active ontology patterns and their source events
4. **Probability Tree** — full Bayesian posterior derivation (the auditable trace)
5. **Object Explorer** — knowledge graph entity browser

---

## 🏗️ Architecture

```
El-druin/
├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── api/routes/          # REST endpoints
│   │   │   ├── analysis.py      # POST /api/v1/evented/analyze
│   │   │   ├── intelligence.py  # Bayesian bridge / probability tree
│   │   │   └── provenance.py    # Entity/relationship provenance
│   │   └── core/                # Config, logging
│   ├── intelligence/            # Core reasoning engine
│   │   ├── evented_pipeline.py  # Five-stage pipeline (Stage 1-3)
│   │   ├── pattern_i18n.py      # CJK -> English pattern display mapping
│   │   ├── probability_tree.py  # Bayesian posterior computation
│   │   └── ontology_forecaster.py # Multi-step Markov simulation
│   ├── knowledge_layer/
│   │   └── entity_resolver.py   # Fuzzy entity deduplication (SIMILARITY=0.85)
│   └── ontology/
│       └── relation_schema.py   # Pattern registry, composition_table, inverse_table
├── frontend/                    # Streamlit UI
│   ├── app.py                   # Main entry point
│   ├── pages/
│   │   └── 3_Object_Explorer.py
│   └── components/
│       ├── faceted_search.py
│       ├── object_view.py
│       └── proof_panel.py
├── experiments/                 # Reproducible baseline experiments
│   ├── news_samples.jsonl       # 10 public news excerpts (URL + metadata)
│   ├── run_baseline.py          # EL-DRUIN + GPT-4 runner
│   ├── compute_metrics.py       # Metrics table generator
│   └── README.md                # Experiment instructions
└── tests/                       # Pytest test suite
    ├── test_evented_pipeline.py
    ├── test_llm_rendering.py    # Guardrail tests (CJK, entity, numeric)
    └── test_pipeline_schema_contract.py
```

### Five-Stage Reasoning Pipeline

```
Input: News Text
    |
    v
Stage 1: Event Extraction
  Rule-based keyword co-occurrence -> EventNode{type, confidence, evidence}
    |
    v
Stage 2a: Pattern Activation
  EventType -> PatternNode  (ontology prior x event confidence)
    |
    +-----------------------------+--------------------+
    |                             |                    |
Stage 2b:                    Stage 2c:           Stage 2d:
Transition Enumeration       State Vector        Driving Factors
(composition_table)          (8D Lie algebra)    (mechanism_class aggregation)
    |
    v
Stage 3: Bayesian Conclusion Generation
  w_t = pi(A) * pi(B) * lie_sim(A,B,C) * lambda^t
  -> alpha/beta paths -> composite_confidence -> compute_trace_ref
  -> LLM rendering pass (with CJK / entity / numeric guardrails)
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and set:

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | LLM backend (`openai` / `groq` / `none`) | `none` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `GROQ_API_KEY` | Groq API key | — |
| `GRAPH_BACKEND` | Graph DB (`kuzu` / `networkx`) | `kuzu` |
| `KUZU_DB_PATH` | KuzuDB path | `./data/kuzu_db` |
| `NEWSAPI_KEY` | NewsAPI key for live feed | — |
| `API_PORT` | Backend port | `8001` |

The pipeline runs fully deterministically without any API key (`LLM_PROVIDER=none`).  
An LLM key enables the rendering pass (paraphrase layer), which is subject to all guardrails.

---

## 🧪 Running Tests

```bash
pip install pytest
PYTHONPATH=backend python -m pytest tests/ -q --ignore=tests/test_deduction_engine.py
```

Key test files:

| File | Coverage |
|---|---|
| `test_evented_pipeline.py` | Stage 1-3 pipeline, pattern activation, credibility |
| `test_llm_rendering.py` | CJK leakage guard, entity invention guard, numeric guard, sentence-length guard |
| `test_pipeline_schema_contract.py` | API output schema backward compatibility |
| `test_grounded_deduce_endpoint.py` | REST endpoint integration |

---

## 🔬 Baseline Experiments

See [`experiments/README.md`](experiments/README.md) for full instructions.

**Quick run (EL-DRUIN only, no API key):**
```bash
python experiments/run_baseline.py --skip-gpt
python experiments/compute_metrics.py
```

**Full run with GPT-4:**
```bash
export OPENAI_API_KEY="sk-..."
python experiments/run_baseline.py
python experiments/compute_metrics.py
```

Results are saved to `experiments/results/` and a Markdown comparison table is written to `experiments/comparison_table.md`.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Streamlit (Python) |
| **Backend API** | FastAPI + Uvicorn |
| **Knowledge Graph** | KuzuDB (embedded) / NetworkX (fallback) |
| **Reasoning Engine** | Pure Python (NumPy for Lie algebra vectors) |
| **LLM Integration** | OpenAI API / Groq API (optional rendering pass) |
| **Testing** | Pytest |
| **Containerisation** | Docker + Docker Compose |

---

## 📋 Feature Kanban

### Done
- [x] 18-pattern CARTESIAN_PATTERN_REGISTRY with composition_table and inverse_table
- [x] Five-stage evented reasoning pipeline
- [x] Bayesian posterior with step decay (compute_trace_ref in every output)
- [x] 8D Lie algebra state vectors and Lie-bracket transition scoring
- [x] Attractor / fixed-point detection
- [x] Phase transition and bifurcation detection
- [x] English-only user-facing outputs (CJK -> English mapping layer)
- [x] CJK leakage guardrail + test
- [x] Invented entity guardrail + test
- [x] Numeric consistency guardrail + test
- [x] KuzuDB knowledge graph with fuzzy entity deduplication
- [x] Five-tab Streamlit UI
- [x] Reproducible baseline experiment framework (EL-DRUIN vs GPT-4)
- [x] 10-sample geopolitical news dataset (public URLs + short excerpts)
- [x] Comparison metrics table (traceability / stability / constraint compliance)

### In Progress
- [ ] Demo GIFs / screenshots
- [ ] Streamlit Cloud deployment

### Planned
- [ ] Learned pattern vectors (from labelled event data)
- [ ] Historical backtesting against outcome datasets
- [ ] Extended composition table (currently ~4% coverage)
- [ ] Group / Hopf-algebra extension for inverse completion
- [ ] Multi-horizon forecasting with confidence intervals

---

## 📄 License

This project is licensed under the **Apache License 2.0** — see [LICENSE](LICENSE) for details.

---

## 📚 Citation

If you use EL-DRUIN in your research, please cite:

```bibtex
@misc{wu2024eldruin,
  title  = {Ontological Trajectory Forecasting via Finite Semigroup Iteration
             and Lie Algebra Approximation in Geopolitical Knowledge Graphs},
  author = {Wu, Qihang},
  year   = {2024},
  institution = {The Hong Kong Polytechnic University},
  url    = {https://github.com/wuqihang-brave/El-druin}
}
```

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.  
All contributions must pass the existing test suite:

```bash
PYTHONPATH=backend python -m pytest tests/ -q --ignore=tests/test_deduction_engine.py
```

---

*EL-DRUIN — named after the magical sword of pure light in the Forgotten Realms universe, symbolising clarity and verifiability in intelligence analysis.*
