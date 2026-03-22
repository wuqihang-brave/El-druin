# EL'druin Intelligence Platform — Deployment Guide

## Quick Start with Docker Compose

### Prerequisites
- Docker 24+
- Docker Compose 2.20+
- 4 GB RAM minimum (8 GB recommended)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/El-druin.git
cd El-druin
cp .env.example .env
```

Edit `.env` and set at minimum:
```bash
POSTGRES_PASSWORD=choose-a-strong-password
NEO4J_PASSWORD=choose-a-strong-password
JWT_SECRET_KEY=generate-32-char-random-string
ANONYMIZATION_SALT=generate-random-salt
```

### 2. Start core services (no Kafka)

```bash
docker compose --profile basic up -d
```

This starts: `postgres`, `neo4j`, `redis`, `backend`.

### 3. Start full stack with streaming

```bash
docker compose --profile streaming up -d
```

This adds `zookeeper` and `kafka` to the above.

### 4. Verify health

```bash
curl http://localhost:8000/health
# {"status":"ok","environment":"development","timestamp":"..."}
```

### 5. Access services

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| API | http://localhost:8000 | — |
| Swagger UI | http://localhost:8000/docs | — |
| Neo4j Browser | http://localhost:7474 | neo4j / (from .env) |
| PostgreSQL | localhost:5432 | (from .env) |
| Redis | localhost:6379 | — |
| Kafka | localhost:9092 | — |

---

## Production Deployment Guide

### Infrastructure Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Backend replicas | 2 | 4+ |
| CPU per replica | 2 vCPU | 4 vCPU |
| RAM per replica | 2 GB | 4 GB |
| PostgreSQL | db.t3.medium | db.r6g.large |
| Neo4j | 4 vCPU / 8 GB | 8 vCPU / 16 GB |
| Redis | cache.t3.small | cache.r6g.large |
| Kafka | 3 brokers, 4 vCPU each | 3 brokers, 8 vCPU each |

### Container Registry

Build and push the backend image:

```bash
docker build -t your-registry/eldruin-backend:1.0.0 ./backend
docker push your-registry/eldruin-backend:1.0.0
```

### Kubernetes Deployment (example)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eldruin-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: eldruin-backend
  template:
    metadata:
      labels:
        app: eldruin-backend
    spec:
      containers:
        - name: backend
          image: your-registry/eldruin-backend:1.0.0
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: eldruin-secrets
            - configMapRef:
                name: eldruin-config
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2000m"
              memory: "4Gi"
          securityContext:
            runAsNonRoot: true
            runAsUser: 1001
            readOnlyRootFilesystem: true
```

### Secrets Management

Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets) — never commit secrets to source control.

Example with AWS Secrets Manager + External Secrets Operator:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: eldruin-secrets
spec:
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: eldruin-secrets
  data:
    - secretKey: JWT_SECRET_KEY
      remoteRef:
        key: eldruin/production
        property: jwt_secret_key
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | — | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | — | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DATABASE_URL` | ✓ | — | PostgreSQL async connection URL |
| `NEO4J_URL` | ✓ | — | Neo4j bolt URL |
| `NEO4J_USER` | ✓ | — | Neo4j username |
| `NEO4J_PASSWORD` | ✓ | — | Neo4j password |
| `REDIS_URL` | ✓ | — | Redis connection URL |
| `JWT_SECRET_KEY` | ✓ | — | JWT signing secret (256-bit min) |
| `JWT_ALGORITHM` | — | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `30` | Token lifetime |
| `ANONYMIZATION_SALT` | ✓ | — | Salt for pseudonymisation |
| `KAFKA_BOOTSTRAP_SERVERS` | — | `localhost:9092` | Kafka broker list |
| `KAFKA_TOPIC_EVENTS` | — | `eldruin.events` | Inbound events topic |
| `OPENAI_API_KEY` | — | — | Required for LLM-powered agents |
| `PINECONE_API_KEY` | — | — | Required when `ENABLE_PINECONE=true` |
| `CORS_ORIGINS` | — | `["http://localhost:3000"]` | Allowed origins (JSON array) |
| `ENABLE_KAFKA_STREAMING` | — | `false` | Enable Kafka consumer |
| `ENABLE_NEO4J` | — | `true` | Enable Neo4j knowledge graph |
| `ENABLE_PINECONE` | — | `false` | Use Pinecone instead of pgvector |
| `ENABLE_MULTIMODAL` | — | `false` | Enable media/geospatial processing |

---

## Database Migration Guide

EL'druin uses Alembic for schema migrations.

### Initial setup

```bash
cd backend
alembic upgrade head
```

### Creating a new migration

```bash
alembic revision --autogenerate -m "add risk_score to events"
# Review the generated file in alembic/versions/
alembic upgrade head
```

### Rolling back

```bash
alembic downgrade -1   # one step back
alembic downgrade base  # all the way back
```

### Production migration checklist

1. Take a database backup before running migrations.
2. Run `alembic upgrade head` before deploying new backend replicas.
3. Ensure migrations are backward-compatible (add columns with defaults; never drop in the same release).

---

## Monitoring Setup

### Health Endpoint

The `/health` endpoint is suitable for load balancer health checks and uptime monitors.

### Prometheus Metrics

Expose metrics by adding `prometheus-fastapi-instrumentator` to `requirements.txt` and uncommenting the metrics middleware in `app/main.py`.

Default metrics available at `GET /metrics`:
- `http_requests_total`
- `http_request_duration_seconds`
- `http_requests_in_progress`

### Recommended Alerts

| Alert | Threshold | Severity |
|-------|-----------|----------|
| API error rate > 5% | 5 min window | critical |
| p95 latency > 2 s | 5 min window | warning |
| Health check failing | 2 consecutive failures | critical |
| PostgreSQL connection pool exhausted | — | critical |
| Kafka consumer lag > 10,000 | — | warning |
| Redis memory > 80% | — | warning |

### Logging

All logs are structured JSON, suitable for ingestion by ELK/OpenSearch, Datadog, or Cloud Logging.

Set `LOG_LEVEL=DEBUG` during troubleshooting (never in production due to PII exposure risk).

---

## Backup and Recovery

### PostgreSQL

```bash
# Backup
pg_dump -h localhost -U eldruin -d eldruin -Fc -f eldruin_$(date +%Y%m%d).dump

# Restore
pg_restore -h localhost -U eldruin -d eldruin eldruin_20240115.dump
```

Automate with `pg_basebackup` or managed service snapshots (RDS automated backups).

### Neo4j

```bash
# Online backup (requires Enterprise) or offline:
docker exec eldruin-neo4j neo4j-admin database dump neo4j --to-path=/backups

# Restore
docker exec eldruin-neo4j neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
```

### Redis

Redis persistence is configured with AOF (`--appendonly yes`). Back up the AOF file volume. For cache-only deployments, Redis data can be rebuilt from the primary stores.
