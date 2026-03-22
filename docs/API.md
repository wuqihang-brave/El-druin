# EL'druin Intelligence Platform — API Documentation

## Overview

The EL'druin REST API provides programmatic access to the intelligence platform's core capabilities: event ingestion, knowledge graph queries, multi-agent analysis, predictions, watchlists, and real-time streaming.

**Base URL:** `http://localhost:8000/api/v1`
**OpenAPI / Swagger UI:** `http://localhost:8000/docs`
**ReDoc:** `http://localhost:8000/redoc`

---

## Authentication

All endpoints (except `/health` and `/api/v1/auth/token`) require a **JWT Bearer token**.

### Obtaining a Token

```http
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

username=analyst@example.com&password=secret
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using the Token

Include the token in every request:
```http
Authorization: Bearer <access_token>
```

### Error Responses

| Code | Meaning |
|------|---------|
| `401` | Token missing or expired |
| `403` | Insufficient permissions / clearance |

---

## Rate Limiting

- Default: **100 requests per 60 seconds** per authenticated user
- Headers returned on every response:
  - `X-RateLimit-Limit: 100`
  - `X-RateLimit-Remaining: 97`
  - `X-RateLimit-Reset: 1700000060`
- When exceeded: `HTTP 429 Too Many Requests`

---

## Endpoints

### Health

#### `GET /health`
Returns platform health status. No authentication required.

**Response:**
```json
{
  "status": "ok",
  "environment": "production",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

---

### Authentication

#### `POST /api/v1/auth/token`
Obtain a JWT access token.

**Request (form-encoded):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | ✓ | User email or username |
| `password` | string | ✓ | Password |

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** `401` Invalid credentials

---

#### `POST /api/v1/auth/register`
Register a new user.

**Request Body:**
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "StrongPass123!",
  "tenant_id": "my-org"
}
```

**Response:** `201 Created`
```json
{
  "id": "usr-uuid",
  "username": "alice",
  "email": "alice@example.com",
  "roles": ["viewer"],
  "clearance_level": "internal",
  "tenant_id": "my-org"
}
```

---

#### `GET /api/v1/auth/me`
Get current user profile.

**Response:**
```json
{
  "user_id": "usr-uuid",
  "username": "alice",
  "roles": ["analyst"],
  "clearance_level": "confidential",
  "tenant_id": "my-org"
}
```

---

### Events

#### `POST /api/v1/events/`
Ingest a new intelligence event.

**Request Body:**
```json
{
  "source": "worldmonitor",
  "title": "Political unrest in Region X",
  "description": "Protests erupted following disputed election results...",
  "event_type": "POLITICAL",
  "severity": "high",
  "location": "Region X, Country Y",
  "entities": ["entity-uuid-1", "entity-uuid-2"],
  "tags": ["election", "protests", "unrest"],
  "metadata": {
    "source_url": "https://...",
    "confidence": 0.87
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "evt-uuid",
  "source": "worldmonitor",
  "title": "Political unrest in Region X",
  "event_type": "POLITICAL",
  "severity": "high",
  "location": "Region X, Country Y",
  "entities": ["entity-uuid-1"],
  "tags": ["election"],
  "embedding_id": "emb-uuid",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Errors:** `400` Validation error, `401` Unauthorized

---

#### `GET /api/v1/events/`
List events with filtering and pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | string | — | Filter by type (POLITICAL, ECONOMIC, ...) |
| `severity` | string | — | Filter by severity (low, medium, high, critical) |
| `source` | string | — | Filter by source name |
| `limit` | int | 20 | Page size (max 100) |
| `offset` | int | 0 | Pagination offset |
| `from_date` | datetime | — | ISO 8601 start date |
| `to_date` | datetime | — | ISO 8601 end date |

**Response:**
```json
{
  "items": [ { "id": "evt-uuid", "title": "...", "severity": "high" } ],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

---

#### `GET /api/v1/events/{event_id}`
Get a single event by ID.

**Response:** Single event object (see POST response schema).

**Errors:** `404` Event not found

---

#### `PUT /api/v1/events/{event_id}`
Update an existing event.

**Request Body:** Partial event fields to update.

**Response:** Updated event object.

**Errors:** `404` Not found, `403` Insufficient permissions

---

#### `DELETE /api/v1/events/{event_id}`
Delete an event. Requires `admin` role.

**Response:** `204 No Content`

**Errors:** `403` Forbidden, `404` Not found

---

#### `GET /api/v1/events/search`
Semantic vector search over events.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | ✓ | Natural language query |
| `limit` | int | 10 | Number of results |
| `threshold` | float | 0.7 | Similarity threshold |

**Response:**
```json
{
  "query": "political instability Middle East",
  "results": [
    {
      "id": "evt-uuid",
      "title": "...",
      "similarity_score": 0.92,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### Knowledge Graph

#### `GET /api/v1/kg/entities`
List entities in the knowledge graph.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_class` | string | — | Filter by class (Person, Organization, Event, Location, Asset) |
| `limit` | int | 20 | Page size (max 100) |
| `skip` | int | 0 | Skip offset |

**Response:**
```json
[
  {
    "id": "ent-uuid",
    "entity_class": "Person",
    "name": "Jane Doe",
    "properties": { "role": "CEO", "nationality": "US" },
    "relationships": [],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

#### `POST /api/v1/kg/entities`
Create a new entity in the knowledge graph.

**Request Body:**
```json
{
  "entity_class": "Organization",
  "name": "Acme Corp",
  "properties": {
    "industry": "Technology",
    "country": "US",
    "founded": 2001
  }
}
```

**Response:** `201 Created` — entity object.

---

#### `GET /api/v1/kg/entities/{entity_id}`
Get a single entity by ID including relationships.

**Response:** Full entity object with relationships.

---

#### `PUT /api/v1/kg/entities/{entity_id}`
Update an existing entity's properties.

---

#### `DELETE /api/v1/kg/entities/{entity_id}`
Delete an entity (admin only).

---

#### `POST /api/v1/kg/relationships`
Create a relationship between two entities.

**Request Body:**
```json
{
  "from_entity_id": "ent-uuid-1",
  "to_entity_id": "ent-uuid-2",
  "relationship_type": "AFFILIATED_WITH",
  "properties": {
    "since": "2020-01-01",
    "confidence": 0.9
  }
}
```

**Response:** `201 Created` — relationship object.

---

#### `GET /api/v1/kg/graph`
Get a subgraph around a focal entity.

**Query Parameters:** `entity_id` (required), `depth` (default 2, max 4)

**Response:**
```json
{
  "nodes": [ { "id": "ent-uuid", "entity_class": "Person", "name": "..." } ],
  "edges": [ { "from": "ent-uuid-1", "to": "ent-uuid-2", "type": "KNOWS" } ]
}
```

---

### Analysis

#### `POST /api/v1/analysis/`
Trigger multi-agent intelligence analysis.

**Request Body:**
```json
{
  "analysis_type": "geopolitical_risk",
  "entity_ids": ["ent-uuid-1", "ent-uuid-2"],
  "event_ids": ["evt-uuid-1"],
  "parameters": {
    "depth": "comprehensive",
    "agents": ["historical", "causal", "economic", "geopolitical"],
    "time_horizon": "6_months"
  }
}
```

**Response:**
```json
{
  "id": "analysis-uuid",
  "analysis_type": "geopolitical_risk",
  "result": {
    "consensus_confidence": 0.82,
    "final_prediction": "Moderate escalation risk over 6-month horizon...",
    "agreement_score": 0.78,
    "key_insights": ["...", "..."],
    "agent_breakdown": {
      "historical": 0.79,
      "causal": 0.85
    }
  },
  "methodology": "multi-agent consensus with weighted averaging",
  "confidence": 0.82,
  "execution_time_ms": 3240,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /api/v1/analysis/`
List past analyses.

**Query Parameters:** `limit`, `offset`, `analysis_type`

---

#### `GET /api/v1/analysis/{analysis_id}`
Get a specific analysis result.

---

### Predictions

#### `POST /api/v1/predictions/`
Generate a structured prediction.

**Request Body:**
```json
{
  "title": "Q2 Stability Assessment",
  "entity_ids": ["ent-uuid-1"],
  "event_ids": ["evt-uuid-1", "evt-uuid-2"],
  "prediction_horizon": "90_days",
  "methodology": "ensemble"
}
```

**Response:** `201 Created`
```json
{
  "id": "pred-uuid",
  "title": "Q2 Stability Assessment",
  "consensus_confidence": 0.76,
  "final_prediction": "Expect continued volatility with 73% probability of...",
  "agents_results": [
    {
      "agent_type": "historical",
      "analysis": "Historical precedent suggests...",
      "confidence": 0.79,
      "evidence": ["..."]
    }
  ],
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /api/v1/predictions/`
List predictions with pagination.

---

#### `GET /api/v1/predictions/{prediction_id}`
Retrieve a specific prediction.

---

### Watchlist

#### `POST /api/v1/watchlist/`
Create a watchlist entry.

**Request Body:**
```json
{
  "entity_id": "ent-uuid",
  "entity_name": "Acme Corp",
  "entity_type": "Organization",
  "notes": "Monitor for M&A activity"
}
```

**Response:** `201 Created` — watchlist item.

---

#### `GET /api/v1/watchlist/`
Get current user's watchlist items.

---

#### `DELETE /api/v1/watchlist/{item_id}`
Remove an item from the watchlist.

---

#### `POST /api/v1/watchlist/{watchlist_id}/alerts`
Add an alert rule to a watchlist entry.

**Request Body:**
```json
{
  "condition": "severity >= high",
  "notification_channel": "email",
  "threshold": 0.7,
  "cooldown_minutes": 60
}
```

---

#### `GET /api/v1/watchlist/{watchlist_id}/alerts`
List alert rules for a watchlist entry.

---

## WebSocket Connections

### Real-Time Event Stream

```
ws://localhost:8000/ws/events?token=<jwt_token>
```

**Message format (server → client):**
```json
{
  "type": "event",
  "payload": {
    "id": "evt-uuid",
    "title": "New event detected",
    "severity": "high",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Real-Time Analysis Updates

```
ws://localhost:8000/ws/analysis/{analysis_id}?token=<jwt_token>
```

Streams incremental analysis results as each agent completes.

---

## Error Response Format

All error responses follow this structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "RESOURCE_NOT_FOUND",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created |
| `204` | No Content |
| `400` | Bad Request / Validation Error |
| `401` | Unauthorized — token missing or invalid |
| `403` | Forbidden — insufficient permissions |
| `404` | Resource not found |
| `422` | Unprocessable Entity — schema validation failure |
| `429` | Too Many Requests |
| `500` | Internal Server Error |
