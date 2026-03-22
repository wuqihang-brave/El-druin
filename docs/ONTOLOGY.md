# EL'druin Intelligence Platform — Ontology Documentation

## Overview

The EL'druin ontology is a formal, extensible schema that defines how real-world entities, events, and their relationships are represented in the knowledge graph. The ontology engine (`OntologyEngine`) enforces schema consistency, validates data at ingest, and applies role-based perspectives to control what each user sees.

---

## Ontology Design Patterns

### Entity-Centric Modelling
Every piece of information is anchored to a typed entity. Relationships between entities are first-class citizens, not embedded attributes.

### Multi-Perspective Views
A single underlying entity graph is exposed through "lenses" (perspectives) tailored to different roles. An analyst perspective might expose financial data; a logistics perspective exposes movement data.

### Progressive Disclosure
Clearance levels gate which properties of an entity are visible. Higher-clearance fields are stripped at query time by the access control layer before the response leaves the API.

### Closed-World Validation
Entity instances are validated against their class definition at ingest. Unknown fields are rejected unless the class is configured with `allow_extra=True`.

---

## Built-In Entity Classes

### Person

Represents a natural person of intelligence interest.

| Property | Type | Required | Clearance | Description |
|----------|------|----------|-----------|-------------|
| `name` | string | ✓ | internal | Full name |
| `aliases` | array[string] | — | internal | Known aliases |
| `nationality` | string | — | internal | Primary nationality |
| `date_of_birth` | date | — | confidential | Date of birth |
| `roles` | array[string] | — | internal | Known roles / titles |
| `affiliation_ids` | array[entity_id] | — | internal | Links to Organizations |
| `risk_score` | float | — | confidential | Calculated risk score 0–1 |
| `passport_numbers` | array[string] | — | secret | Passport identifiers |

**Validation Rules:**
- `name` must be non-empty
- `risk_score` must be in [0.0, 1.0]
- `date_of_birth` must be a valid ISO 8601 date

---

### Organization

Represents a legal entity, group, or institution.

| Property | Type | Required | Clearance | Description |
|----------|------|----------|-----------|-------------|
| `name` | string | ✓ | internal | Organization name |
| `aliases` | array[string] | — | internal | Trade names, abbreviations |
| `industry` | string | — | internal | Industry sector |
| `country` | string | — | internal | Country of registration |
| `founded` | integer | — | internal | Year founded |
| `size` | enum | — | internal | micro/small/medium/large/enterprise |
| `sanctions_status` | enum | — | confidential | none/listed/under_review |
| `beneficial_owners` | array[entity_id] | — | secret | Links to Person entities |
| `risk_score` | float | — | confidential | Calculated risk score 0–1 |

---

### Event

Represents an observable real-world occurrence.

| Property | Type | Required | Clearance | Description |
|----------|------|----------|-----------|-------------|
| `title` | string | ✓ | internal | Short event title |
| `description` | string | — | internal | Full description |
| `event_type` | enum | ✓ | internal | See Event Types below |
| `severity` | enum | ✓ | internal | low/medium/high/critical |
| `location` | string | — | internal | Human-readable location |
| `entities` | array[entity_id] | — | internal | Involved entities |
| `source` | string | ✓ | internal | Data source identifier |
| `confidence` | float | — | internal | Source confidence 0–1 |
| `tags` | array[string] | — | internal | Free-text tags |

**Event Types:**
`POLITICAL`, `ECONOMIC`, `SECURITY`, `MILITARY`, `NATURAL_DISASTER`, `CYBER`, `SOCIAL`, `ENVIRONMENTAL`, `FINANCIAL`, `DIPLOMATIC`

---

### Location

Represents a geographic place.

| Property | Type | Required | Clearance | Description |
|----------|------|----------|-----------|-------------|
| `name` | string | ✓ | internal | Place name |
| `country_code` | string | — | internal | ISO 3166-1 alpha-2 |
| `latitude` | float | — | internal | WGS84 latitude |
| `longitude` | float | — | internal | WGS84 longitude |
| `location_type` | enum | — | internal | city/region/country/facility/coordinate |
| `address` | string | — | internal | Street address |
| `geojson` | object | — | internal | GeoJSON polygon/point |

---

### Asset

Represents a physical or digital asset under surveillance.

| Property | Type | Required | Clearance | Description |
|----------|------|----------|-----------|-------------|
| `name` | string | ✓ | internal | Asset name or identifier |
| `asset_type` | enum | ✓ | internal | vessel/aircraft/vehicle/infrastructure/digital |
| `identifier` | string | — | internal | IMO number, tail number, VIN, etc. |
| `owner_id` | entity_id | — | confidential | Link to Person or Organization |
| `flag_state` | string | — | internal | Flag/registration country |
| `status` | enum | — | internal | active/inactive/sanctioned/unknown |
| `last_location_id` | entity_id | — | internal | Link to Location |
| `risk_score` | float | — | confidential | Calculated risk score 0–1 |

---

## Relationship Types

| Relationship | From | To | Properties |
|-------------|------|----|-----------|
| `AFFILIATED_WITH` | Person | Organization | `since`, `role`, `confidence` |
| `OWNS` | Person / Organization | Asset | `since`, `share_pct`, `beneficial` |
| `LOCATED_AT` | Person / Organization / Asset | Location | `as_of`, `confidence` |
| `PARTICIPATED_IN` | Person / Organization | Event | `role`, `confirmed` |
| `KNOWS` | Person | Person | `relationship_type`, `strength` |
| `CONTROLS` | Person / Organization | Organization | `control_type`, `since` |
| `ASSOCIATED_WITH` | Any | Any | `association_type`, `confidence` |
| `CAUSED_BY` | Event | Event | `causality_score` |
| `PRECEDED_BY` | Event | Event | — |
| `OCCURRED_AT` | Event | Location | `confidence` |

---

## Property Validation Rules

The `OntologyEngine` applies the following rule types at validation time:

| Rule | Parameter | Behaviour |
|------|-----------|-----------|
| `required` | `true` / `false` | Field must be present and non-null |
| `type` | `string`, `integer`, `float`, `boolean`, `date`, `array`, `object` | Python type check |
| `min` | numeric | Minimum value (inclusive) |
| `max` | numeric | Maximum value (inclusive) |
| `min_length` | integer | Minimum string length |
| `max_length` | integer | Maximum string length |
| `pattern` | regex string | Must match pattern |
| `enum` | array | Value must be one of the listed options |
| `items_type` | string | Element type for array properties |

**Example class definition:**
```python
engine.define_entity_class(
    name="Person",
    properties={
        "name": {"type": "string"},
        "risk_score": {"type": "float"},
    },
    validation_rules={
        "name": {"required": True, "min_length": 1, "max_length": 200},
        "risk_score": {"min": 0.0, "max": 1.0},
    },
    classification="internal",
)
```

---

## Multi-Perspective Views

Perspectives are named views that restrict which entity fields are exposed based on the requesting user's role and clearance.

```python
engine.create_perspective(
    name="logistics_view",
    entity_filters={
        "Asset": ["name", "asset_type", "identifier", "last_location_id", "status"],
        "Location": ["name", "latitude", "longitude"],
    },
    role_required="analyst",
    clearance_required="internal",
)
```

**Built-in perspectives:**

| Perspective | Roles | Description |
|-------------|-------|-------------|
| `default` | viewer | Basic non-sensitive fields |
| `analyst_view` | analyst | Adds risk scores, affiliations |
| `admin_view` | admin | All fields including secret-cleared |
| `logistics_view` | analyst | Asset movement and location focus |
| `financial_view` | analyst | Ownership, beneficial owner, financial data |

---

## Data Lineage Tracking

Every entity maintains a lineage record that captures:
- **Sources**: Which data feeds contributed to this entity
- **Transformations**: Which enrichment or normalisation steps were applied
- **Creation timestamp**: When first ingested
- **Modification history**: Ordered list of change log IDs (via audit trail)

```python
lineage = await ontology_engine.get_lineage("entity-uuid")
print(lineage.sources)          # ["worldmonitor", "mirofish"]
print(lineage.transformations)  # ["geocoded", "entity_linked", "sentiment_scored"]
print(lineage.created_at)       # "2024-01-15T08:22:00Z"
```

Lineage data is linked to the `audit_logs` table in PostgreSQL for a complete, tamper-evident chain.
