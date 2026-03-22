# EL'druin Intelligence Platform — Architecture

## System Overview

EL'druin is a multi-layered intelligence platform that combines ontology-driven data modeling, multi-agent AI analysis, and real-time streaming to deliver actionable intelligence at enterprise scale.

```
╔══════════════════════════════════════════════════════════════════╗
║                     EXTERNAL DATA SOURCES                        ║
║  WorldMonitor API    MiroFish API    Custom Sources    Webhooks  ║
╚══════════════╤══════════════╤════════════════╤═══════════════════╝
               │              │                │
               ▼              ▼                ▼
╔══════════════════════════════════════════════════════════════════╗
║                      INTEGRATION LAYER                           ║
║         Adapters    Schema Normalization    Rate Limiting         ║
╚══════════════════════════════╤═══════════════════════════════════╝
                               │
               ┌───────────────┴────────────────┐
               ▼                                ▼
╔══════════════════════╗        ╔═══════════════════════════════╗
║   STREAMING ENGINE   ║        ║      REST API (FastAPI)       ║
║  Kafka Consumer      ║        ║  /api/v1/events               ║
║  Deduplication       ║        ║  /api/v1/kg                   ║
║  Enrichment          ║        ║  /api/v1/analysis             ║
║  Anomaly Detection   ║        ║  /api/v1/predictions          ║
╚══════════╤═══════════╝        ║  /api/v1/watchlist            ║
           │                   ║  WebSocket /ws/*              ║
           ▼                   ╚═══════════════╤═══════════════╝
╔══════════════════════════════════════════════╤═══════════════════╗
║                    CORE INTELLIGENCE LAYER                        ║
║                                                                   ║
║  ┌─────────────────┐   ┌─────────────────────────────────────┐   ║
║  │ Ontology Engine │   │      Multi-Agent Analysis           │   ║
║  │ Entity Classes  │   │  Historical │ Causal │ Sentiment     │   ║
║  │ Perspectives    │   │  Economic   │ Geopolitical           │   ║
║  │ Validation      │   │  ────────────────────────────────── │   ║
║  └─────────────────┘   │       Consensus Engine              │   ║
║                        └─────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════╝
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
╔══════════════╗   ╔═══════════════════╗   ╔═══════════════╗
║  PostgreSQL  ║   ║      Neo4j        ║   ║    Redis      ║
║  + pgvector  ║   ║  Knowledge Graph  ║   ║  Cache/Dedup  ║
║  Events      ║   ║  Entities         ║   ║  Sessions     ║
║  Predictions ║   ║  Relationships    ║   ║  Rate Limits  ║
║  Audit Logs  ║   ║  Graph Queries    ║   ╚═══════════════╝
╚══════════════╝   ╚═══════════════════╝
           │
           ▼
╔══════════════════════════════════════════════════════════════════╗
║                      SECURITY LAYER                              ║
║  ABAC Engine    Audit Logger    JWT Auth    Data Governance      ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Component Descriptions

### API Gateway (FastAPI)
The REST API layer built with FastAPI and served by Uvicorn. Handles authentication, request validation, rate limiting, and routes to appropriate service handlers. WebSocket support enables real-time event streaming.

**Key files:** `app/main.py`, `app/api/`

### Ontology Engine
Defines and enforces the enterprise ontology schema. Supports:
- **Entity classes**: Person, Organization, Event, Location, Asset (extensible)
- **Perspectives**: Role-based views that expose different entity properties
- **Validation rules**: Field-level constraints applied at ingest time
- **Data lineage**: Tracks entity provenance through transformations

**Key file:** `app/core/ontology_engine.py`

### Multi-Agent Analysis System
Five specialized AI agents each analyse events from a distinct lens:

| Agent | Focus | Weight |
|-------|-------|--------|
| `HistoricalAnalyst` | Pattern matching against historical precedents | 25% |
| `CausalAnalyst` | Root-cause and causal chain analysis | 25% |
| `EconomicAgent` | Economic indicators and market dynamics | 20% |
| `GeopoliticalAgent` | Political risk and interstate dynamics | 15% |
| `SentimentAgent` | Textual sentiment and narrative analysis | 15% |

The **ConsensusEngine** aggregates results using weighted averaging and detects dissenting agents when confidence deviates by more than the `DISSENT_THRESHOLD` (default 0.20).

**Key files:** `app/agents/`

### Real-Time Streaming Engine
Kafka-based pipeline for high-throughput event ingestion:
1. **Ingest** — Events arrive via REST or Kafka topic
2. **Deduplication** — Redis-backed time-window deduplication (60 s default)
3. **Enrichment** — Geo-coding, entity linking, sentiment scoring
4. **Anomaly Detection** — Statistical outlier detection
5. **Publish** — Enriched events forwarded to downstream topic

**Key file:** `app/core/streaming_engine.py`

### Knowledge Graph (Neo4j)
Stores entities and their typed relationships. Supports:
- Graph traversal queries (shortest path, neighbourhood subgraphs)
- Relationship inference
- Multi-hop analysis for network effects

### Vector Store (PostgreSQL + pgvector / Pinecone)
Stores and queries dense embedding vectors for semantic search. The default backend uses the `pgvector` PostgreSQL extension; Pinecone is optionally supported for cloud-scale deployments.

### Security Layer
- **ABAC Engine**: Attribute-based access control with clearance levels (public → internal → confidential → secret) and role permissions
- **Audit Logger**: Tamper-evident SHA-256 hash-chained audit records
- **Data Governance**: Classification tagging, anonymisation, and GDPR compliance helpers

**Key files:** `app/security/`

### Integration Adapters
Pre-built connectors for external data sources:
- `WorldMonitorAdapter`: REST polling with webhook support
- `MiroFishAdapter`: Maritime/geospatial data feed
- `CustomSourceAdapter`: Generic configurable adapter

**Key files:** `app/integrations/`

---

## Data Flow Pipeline

```
External Source
     │
     ▼
Integration Adapter (auth, schema mapping)
     │
     ▼
Event Validation (OntologyEngine.validate_entity)
     │
     ├──► Kafka topic: eldruin.events
     │         │
     │         ▼
     │    Streaming Engine (dedup → enrich → anomaly detection)
     │         │
     │         ▼
     │    Kafka topic: eldruin.events.enriched
     │
     ├──► PostgreSQL (persist raw event + embedding)
     │
     ├──► Neo4j (upsert entity nodes & relationships)
     │
     └──► Vector Store (store embedding for semantic search)
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| API Framework | FastAPI | 0.104 |
| ASGI Server | Uvicorn | 0.24 |
| ORM | SQLAlchemy (async) | 2.0 |
| Relational DB | PostgreSQL + pgvector | 15 |
| Graph DB | Neo4j Community | 5 |
| Cache / Dedup | Redis | 7 |
| Message Broker | Apache Kafka (Confluent) | 7.5 |
| Embeddings | sentence-transformers | 2.2 |
| Vector Index | pgvector / Pinecone | — |
| LLM Integration | LangChain + OpenAI | GPT-4 |
| Auth | python-jose JWT | 3.3 |
| Password Hashing | passlib bcrypt | 1.7 |
| Configuration | pydantic-settings | 2.1 |
| Container Runtime | Docker / Docker Compose | — |

---

## Scalability Considerations

### Horizontal Scaling
- The FastAPI application is **stateless** — scale by adding replicas behind a load balancer.
- Session state is stored in Redis, not in-process.
- Database connection pooling via SQLAlchemy's async engine.

### Kafka Partitioning
- Partition the `eldruin.events` topic by `source` for parallelism.
- Each backend replica runs its own Kafka consumer within the same group.
- Increase `KAFKA_CONSUMER_GROUP` replicas to scale event processing linearly.

### Read Scaling
- PostgreSQL read replicas can be added; the application supports a separate `DATABASE_READONLY_URL`.
- Redis caches frequent knowledge graph queries with a configurable TTL.

### LLM Cost Management
- Agent calls are gated by feature flags (`ENABLE_LLM`).
- Response caching in Redis avoids re-analysing identical event payloads.
- Token budgets enforced per-analysis via `max_tokens` parameter.

---

## High Availability Design

```
                    ┌──────────────┐
                    │  Load Balancer│
                    └──────┬───────┘
              ┌────────────┤
              ▼            ▼
       ┌──────────┐  ┌──────────┐
       │ Backend 1│  │ Backend 2│    (N replicas)
       └────┬─────┘  └────┬─────┘
            └──────┬───────┘
                   ▼
       ┌───────────────────────┐
       │  PostgreSQL Primary   │──► Read Replica
       │  + pgvector           │
       └───────────────────────┘
       ┌───────────────────────┐
       │   Neo4j Cluster       │   (Enterprise: causal clustering)
       └───────────────────────┘
       ┌───────────────────────┐
       │  Redis Sentinel /     │
       │  Redis Cluster        │
       └───────────────────────┘
       ┌───────────────────────┐
       │  Kafka Cluster        │   (3+ brokers, replication factor 3)
       └───────────────────────┘
```

- **Database**: Primary + replicas; automated failover via Patroni or managed services (RDS, CloudSQL).
- **Neo4j**: Community edition is single-node; Enterprise adds causal clustering.
- **Redis**: Redis Sentinel for HA or Redis Cluster for large datasets.
- **Kafka**: Minimum 3 brokers with `replication.factor=3` in production.
