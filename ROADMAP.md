# EL'druin Intelligence Platform — Roadmap

## Phase 1: Core Framework *(current)*

Foundational data ingestion, storage, analysis, and security layers.

- [x] FastAPI REST API with JWT authentication
- [x] PostgreSQL + pgvector for event storage and semantic search
- [x] Neo4j knowledge graph (entities and relationships)
- [x] Redis caching and deduplication
- [x] Ontology engine with entity validation and multi-perspective views
- [x] Multi-agent analysis system (Historical, Causal, Economic, Geopolitical, Sentiment)
- [x] Consensus engine with weighted averaging and dissent detection
- [x] Real-time streaming engine (Kafka ingest, dedup, enrichment)
- [x] ABAC security engine with clearance levels and tenant isolation
- [x] Tamper-evident audit logger (SHA-256 hash chaining)
- [x] JWT auth + bcrypt password hashing
- [x] WorldMonitor integration adapter
- [x] MiroFish integration adapter
- [x] Custom source / webhook adapter framework
- [x] Docker Compose deployment (basic + streaming profiles)
- [x] Multi-stage production Dockerfile (non-root user)
- [x] Unit and integration test suite

---

## Phase 2: Advanced Analytics

Deeper intelligence capabilities and enriched knowledge representation.

- [ ] Automated entity disambiguation and record linkage
- [ ] Named Entity Recognition (NER) pipeline for unstructured text
- [ ] Causal inference engine with Bayesian network support
- [ ] Graph neural network embeddings for entity similarity
- [ ] Temporal knowledge graph (event sequences and timelines)
- [ ] Influence network analysis (centrality, community detection)
- [ ] Automated hypothesis generation from knowledge graph patterns
- [ ] Confidence calibration and uncertainty quantification
- [ ] Historical baseline modelling and deviation alerts
- [ ] Geospatial clustering and hotspot detection
- [ ] Enhanced watchlist: ML-driven alert scoring and deduplication
- [ ] Alembic database migrations for schema evolution

---

## Phase 3: Multimodal Fusion

Processing and fusing non-textual intelligence sources.

- [ ] Image analysis pipeline (object detection, OCR, satellite imagery)
- [ ] Video clip summarisation and event extraction
- [ ] Audio transcription and speaker identification
- [ ] Document intelligence (PDF/DOC parsing, table extraction)
- [ ] Geospatial raster analysis (heat maps, change detection)
- [ ] AIS vessel track analysis and behavioural modelling
- [ ] Flight tracking integration (ADS-B data fusion)
- [ ] Social media firehose adapter (Twitter/X, Telegram channels)
- [ ] Multimodal embedding fusion (text + image + geo in shared vector space)
- [ ] Report generation with embedded charts and maps

---

## Phase 4: Federation & Scaling

Enabling multi-organisation deployments and global-scale data volumes.

- [ ] Federated query engine (cross-tenant, privacy-preserving)
- [ ] Federated knowledge graph (multi-node Neo4j Enterprise clustering)
- [ ] Data marketplace: controlled sharing of sanitised datasets between tenants
- [ ] Distributed streaming with multi-region Kafka replication
- [ ] GraphQL API layer for flexible client-side querying
- [ ] Webhook pub/sub for downstream system integration
- [ ] gRPC streaming endpoint for high-throughput consumers
- [ ] Horizontal auto-scaling with Kubernetes HPA
- [ ] Read replica routing for analytics workloads
- [ ] Pinecone federated index for cross-tenant semantic search
- [ ] SOC 2 Type II certification readiness

---

## Phase 5: Production Hardening

Operational maturity for mission-critical deployments.

- [ ] Full Prometheus + Grafana observability stack
- [ ] Distributed tracing with OpenTelemetry + Jaeger
- [ ] Chaos engineering test suite (database failover, network partitions)
- [ ] Automated secret rotation (integration with HashiCorp Vault)
- [ ] mTLS for all service-to-service communication
- [ ] FIPS 140-2 compliant cryptographic module option
- [ ] Air-gapped deployment guide (no internet dependency)
- [ ] Automated GDPR right-to-erasure workflow
- [ ] SLA-aware rate limiting and priority queues
- [ ] Compliance dashboards (GDPR, SOC 2, ISO 27001)
- [ ] Red team / penetration test and remediation cycle
- [ ] 99.9% uptime SLA documentation and runbooks
