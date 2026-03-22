# EL'druin Intelligence Platform

> **Enterprise-grade, ontology-driven intelligence — from raw events to actionable insight.**

EL'druin fuses real-time data ingestion, a typed knowledge graph, and a multi-agent AI analysis pipeline into a single platform purpose-built for intelligence professionals. It ingests events from heterogeneous sources, enriches and deduplicates them through a streaming engine, stores relationships in a Neo4j knowledge graph, and generates structured predictions via five specialised AI agents that vote toward a consensus.

---

## Features

| Area | Capability |
|------|-----------|
| **Ontology Engine** | Extensible entity schema (Person, Organization, Event, Location, Asset) with validation rules, multi-perspective views, and data lineage tracking |
| **Knowledge Graph** | Neo4j-backed entity and relationship store with graph traversal and subgraph queries |
| **Multi-Agent Analysis** | Historical, Causal, Economic, Geopolitical, and Sentiment agents with weighted consensus engine |
| **Real-Time Streaming** | Kafka-based ingest pipeline with Redis deduplication, geocoding enrichment, and anomaly detection |
| **Semantic Search** | Dense embedding search via pgvector (PostgreSQL) or Pinecone |
| **Security** | ABAC engine with clearance levels, tamper-evident audit logging, JWT auth, multi-tenancy |
| **Integrations** | Pre-built adapters for WorldMonitor, MiroFish, and generic REST/webhook sources |
| **Multimodal** | Optional media processing and geospatial analysis modules |
| **Collaboration** | Workflow automation, briefing generation, and shared workspaces |

---

## Quick Start

### Prerequisites
- Docker 24+ and Docker Compose 2.20+
- 4 GB RAM minimum

### 1. Configure

```bash
git clone https://github.com/your-org/El-druin.git
cd El-druin
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, NEO4J_PASSWORD, JWT_SECRET_KEY
```

### 2. Start

```bash
# Core services (PostgreSQL, Neo4j, Redis, Backend API)
docker compose --profile basic up -d

# Full stack including Kafka streaming
docker compose --profile streaming up -d
```

### 3. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","environment":"development","timestamp":"..."}
```

### 4. Explore

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Neo4j Browser**: http://localhost:7474

---

## Architecture Overview

```
External Sources → Integration Adapters
                          │
              ┌───────────┴──────────────┐
              ▼                          ▼
     Streaming Engine              REST API (FastAPI)
  (Kafka · Dedup · Enrich)       /api/v1/{events,kg,analysis,...}
              │                          │
              └───────────┬──────────────┘
                          ▼
              ┌─────────────────────────┐
              │   Core Intelligence     │
              │  Ontology · Agents ·    │
              │  Consensus Engine       │
              └──────────┬──────────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
      PostgreSQL        Neo4j         Redis
     (+ pgvector)   (Knowledge      (Cache /
                      Graph)         Dedup)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/API.md](docs/API.md) | Complete REST & WebSocket API reference |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, components, data flow |
| [docs/ONTOLOGY.md](docs/ONTOLOGY.md) | Entity schema, relationships, validation |
| [docs/SECURITY.md](docs/SECURITY.md) | ABAC, audit logging, GDPR, SOC2 |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | WorldMonitor, MiroFish, custom sources |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, Kubernetes, migrations, monitoring |
| [ROADMAP.md](ROADMAP.md) | Feature roadmap by phase |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Unit tests mock all external services (PostgreSQL, Neo4j, Redis, Kafka) and run without any infrastructure.

---

## Project Structure

```
El-druin/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (events, kg, analysis, ...)
│   │   ├── agents/       # Intelligence agents + consensus engine
│   │   ├── core/         # Ontology engine, streaming engine
│   │   ├── db/           # Database clients (postgres, neo4j, redis)
│   │   ├── integrations/ # WorldMonitor, MiroFish, custom adapters
│   │   ├── models/       # SQLAlchemy ORM models + Pydantic schemas
│   │   ├── multimodal/   # Geospatial and media processing
│   │   ├── security/     # ABAC, audit logger, data governance
│   │   ├── collaboration/# Workflows, briefing generator
│   │   ├── config.py     # pydantic-settings configuration
│   │   └── main.py       # FastAPI application entry point
│   ├── Dockerfile
│   └── requirements.txt
├── tests/
│   ├── unit/             # Unit tests (no external services)
│   └── integration/      # Integration tests (mocked services)
├── docs/                 # Project documentation
├── docker-compose.yml
├── .env.example
└── ROADMAP.md
```

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes and add tests.
3. Ensure all tests pass: `pytest tests/ -v`
4. Open a pull request with a clear description of the change.

Please follow the existing code style (black + isort) and add docstrings to all public functions and classes.

---

## License

This project is licensed under the terms specified in [LICENSE](LICENSE).
