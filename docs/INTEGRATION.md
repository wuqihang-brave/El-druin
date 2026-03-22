# EL'druin Intelligence Platform — Integration Guide

## Overview

EL'druin ships with pre-built adapters for WorldMonitor and MiroFish, plus a generic `CustomSourceAdapter` for any REST or webhook-based data feed.

---

## WorldMonitor Integration

WorldMonitor is a geopolitical risk monitoring service. The `WorldMonitorAdapter` polls the WorldMonitor API and converts responses to EL'druin event format.

### Configuration

Set the following environment variables:

```bash
WORLDMONITOR_API_URL=https://api.worldmonitor.example.com
WORLDMONITOR_API_KEY=your-worldmonitor-api-key
```

### How It Works

```python
from app.integrations.worldmonitor_adapter import WorldMonitorAdapter

adapter = WorldMonitorAdapter(
    api_url=settings.WORLDMONITOR_API_URL,
    api_key=settings.WORLDMONITOR_API_KEY,
)

# Fetch recent events
events = await adapter.fetch_events(
    from_date="2024-01-01T00:00:00Z",
    filters={"severity": ["high", "critical"], "regions": ["EMEA"]},
)

# Ingest into EL'druin
result = await streaming_engine.ingest_event_stream("worldmonitor", events)
print(f"Accepted: {result.accepted}, Rejected duplicates: {result.rejected}")
```

### Webhook Setup

WorldMonitor can push events in real time. Configure the webhook endpoint:

1. In your WorldMonitor dashboard, set the webhook URL to:
   ```
   https://your-eldruin-instance.example.com/api/v1/integrations/worldmonitor/webhook
   ```
2. Set the webhook secret to match `WORLDMONITOR_WEBHOOK_SECRET` in your `.env`.
3. EL'druin validates the `X-WorldMonitor-Signature` header using HMAC-SHA256.

### Field Mapping

| WorldMonitor Field | EL'druin Field | Notes |
|-------------------|---------------|-------|
| `event_id` | `metadata.external_id` | Preserved for deduplication |
| `headline` | `title` | — |
| `summary` | `description` | — |
| `category` | `event_type` | Mapped via `WORLDMONITOR_TYPE_MAP` |
| `risk_score` | `metadata.risk_score` | Float 0–1 |
| `affected_countries` | `location` | Joined as comma-separated string |
| `published_at` | `created_at` | ISO 8601 |

---

## MiroFish Integration

MiroFish provides maritime intelligence including vessel tracking, port activity, and anomalous vessel behaviour.

### Configuration

```bash
MIROFISH_API_URL=https://api.mirofish.example.com
MIROFISH_API_KEY=your-mirofish-api-key
```

### Usage

```python
from app.integrations.mirofish_adapter import MiroFishAdapter

adapter = MiroFishAdapter(
    api_url=settings.MIROFISH_API_URL,
    api_key=settings.MIROFISH_API_KEY,
)

# Fetch vessel events in a bounding box
events = await adapter.fetch_vessel_events(
    bbox={"lat_min": -10, "lat_max": 40, "lon_min": -20, "lon_max": 60},
    event_types=["AIS_DARK", "SPOOFING", "PORT_CALL"],
    limit=500,
)
```

### Supported Event Types

| Type | Description |
|------|-------------|
| `AIS_DARK` | Vessel went dark (AIS transponder off) |
| `SPOOFING` | GPS/AIS spoofing detected |
| `SPEED_ANOMALY` | Speed inconsistent with vessel class |
| `PORT_CALL` | Vessel arrived at or departed a port |
| `SANCTIONS_HIT` | Vessel matched sanctions list |

### Entity Enrichment

The MiroFish adapter automatically creates or updates `Asset` entities in the knowledge graph with vessel metadata (IMO number, flag state, vessel type, dimensions).

---

## Custom Data Source Configuration

Use `CustomSourceAdapter` to connect any REST API or webhook feed.

### REST Polling Source

```python
from app.integrations.custom_sources import CustomSourceAdapter

adapter = CustomSourceAdapter(
    source_name="my-news-feed",
    base_url="https://api.mynewsfeed.example.com",
    auth_type="api_key",
    auth_config={"header": "X-API-Key", "value": "secret"},
    # Map the source JSON response to EL'druin schema
    field_mapping={
        "title": "headline",
        "description": "body",
        "event_type": "category",
        "severity": "priority",
        "location": "country",
        "created_at": "published",
    },
    # JSONPath to the list of events in the response
    results_path="$.data.events",
    # Poll every 5 minutes
    poll_interval_seconds=300,
)

await adapter.start_polling()
```

### Webhook Source

Register a webhook receiver:

```python
from app.integrations.custom_sources import WebhookSource

webhook = WebhookSource(
    source_name="internal-siem",
    # HMAC secret for signature verification
    secret="webhook-hmac-secret",
    field_mapping={...},
)
# The endpoint is auto-registered at:
# POST /api/v1/integrations/webhook/{source_name}
```

### Authentication Types

| Type | Config Keys |
|------|------------|
| `api_key` | `header`, `value` |
| `bearer` | `token` |
| `basic` | `username`, `password` |
| `oauth2_client_credentials` | `client_id`, `client_secret`, `token_url` |
| `none` | — |

---

## Webhook Setup (Generic)

All webhook endpoints validate request integrity using HMAC-SHA256:

1. **Shared secret**: Configure `{SOURCE}_WEBHOOK_SECRET` in `.env`.
2. **Signature header**: Source must include `X-Signature: sha256=<hmac>` in requests.
3. **Payload**: JSON body of event(s).

Example signature generation (Python):
```python
import hashlib, hmac

secret = b"your-webhook-secret"
payload = b'{"title": "Event", "severity": "high"}'
sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
headers = {"X-Signature": f"sha256={sig}"}
```

---

## Authentication for External Services

All outbound HTTP requests from integration adapters use **secure credential storage**:

- Credentials are read from environment variables, never hardcoded.
- API keys are stored as `SecretStr` via pydantic-settings to prevent logging.
- OAuth 2.0 tokens are refreshed automatically before expiry.
- mTLS is supported for enterprise integrations (configure `CLIENT_CERT_PATH` and `CLIENT_KEY_PATH`).

### Rotating Credentials

1. Update the environment variable in your secrets manager.
2. Restart the backend service (or use a live-reload mechanism).
3. Old tokens are invalidated on the next API call cycle.

---

## Integration Health Monitoring

Each adapter exposes a health check:

```http
GET /api/v1/integrations/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "worldmonitor": { "status": "ok", "last_poll": "2024-01-15T10:25:00Z", "events_ingested_1h": 147 },
  "mirofish": { "status": "ok", "last_poll": "2024-01-15T10:29:00Z", "events_ingested_1h": 23 },
  "my-news-feed": { "status": "degraded", "error": "Upstream API timeout", "last_success": "2024-01-15T09:50:00Z" }
}
```
