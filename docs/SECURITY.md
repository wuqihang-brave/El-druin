# EL'druin Intelligence Platform — Security Documentation

## Overview

EL'druin implements a defence-in-depth security architecture covering authentication, authorisation, data classification, audit logging, multi-tenancy, and compliance controls.

---

## JWT Authentication

### Token Lifecycle

1. User submits credentials to `POST /api/v1/auth/token`.
2. Server verifies the password hash (bcrypt).
3. A JWT is signed with `JWT_SECRET_KEY` using `JWT_ALGORITHM` (default: HS256).
4. Token expires after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30).
5. Client sends `Authorization: Bearer <token>` on every subsequent request.
6. The `get_current_user` dependency decodes and validates the token on every request.

### Token Claims

```json
{
  "sub": "user-uuid",
  "username": "alice",
  "roles": ["analyst"],
  "clearance_level": "confidential",
  "tenant_id": "my-org",
  "exp": 1700000000
}
```

### Security Requirements

- `JWT_SECRET_KEY` must be at least 32 random bytes in production.
- The application raises `ValueError` at startup if an insecure default is used in `ENVIRONMENT=production`.
- Tokens are **not** revocable by default; implement a Redis blocklist for revocation if required.
- Use HTTPS in all non-local deployments to prevent token interception.

---

## ABAC Policy Framework

EL'druin uses **Attribute-Based Access Control (ABAC)** rather than simple RBAC. Access decisions combine:

1. **User attributes**: roles, clearance level, tenant ID
2. **Resource attributes**: classification level, tenant ID, owner
3. **Action**: read, create, update, delete, export, admin
4. **Registered policies**: custom allow/deny rules

### Clearance Levels (ascending)

| Level | Index | Description |
|-------|-------|-------------|
| `public` | 0 | Non-sensitive, freely accessible |
| `internal` | 1 | Internal use only, default for new entities |
| `confidential` | 2 | Restricted distribution |
| `secret` | 3 | Need-to-know only |

A user may only access resources at or below their clearance level.

### Role Permissions

| Role | Permitted Actions |
|------|------------------|
| `viewer` | read |
| `analyst` | read, create, export |
| `admin` | read, create, update, delete, export, admin |

### Tenant Isolation

- Every entity and event carries a `tenant_id`.
- Users can only access resources within their tenant.
- Admin users bypass tenant isolation (cross-tenant admin operations).

### Custom Policies

Register additional allow/deny policies at runtime:

```python
access_control.register_policy({
    "type": "deny",
    "conditions": [
        {"source": "resource", "attribute": "classification", "operator": "eq", "value": "secret"},
        {"source": "user", "attribute": "clearance_level", "operator": "ne", "value": "secret"},
    ],
})
```

---

## Data Classification Levels

| Classification | Description | Handling |
|---------------|-------------|---------|
| `public` | Publicly releasable | No restrictions |
| `internal` | Internal use only | Not for external sharing |
| `confidential` | Business sensitive | Restricted circulation, audit on access |
| `secret` | Highly sensitive | Need-to-know, full audit trail, export prohibited |

### Column-Level Classification

Individual fields within an entity can be classified independently:

```python
record = {
    "name": "Alice",
    "ssn": "123-45-6789",
    "risk_score": 0.87,
    "_field_classifications": {
        "ssn": "secret",
        "risk_score": "confidential",
        "name": "internal",
    },
}
filtered = access_control.filter_columns(record, user_clearance="confidential")
# ssn is stripped; risk_score and name are returned
```

---

## Audit Logging

### Design

EL'druin's audit logger produces a **tamper-evident, hash-chained** log stored in PostgreSQL.

Each log record contains:
- `id`: UUID
- `event_type`: query / data_export / data_modification / access_denial / admin_action
- `user_id`: Acting user
- `data`: JSON payload of the audited action
- `chain_hash`: `SHA256(prev_hash + record_content)`
- `prev_hash`: Previous record's chain hash
- `created_at`: UTC timestamp

The genesis hash is `"0" * 64`. Any tampering with a record breaks the chain, detectable via `verify_integrity()`.

### Audited Events

| Event Type | Triggered By |
|-----------|-------------|
| `query` | Any data search or list operation |
| `data_export` | Download or export API calls |
| `data_modification` | PUT / PATCH / DELETE operations |
| `access_denial` | Failed access control checks |
| `admin_action` | User management, policy changes |

### Compliance Reports

```python
report = await audit_logger.generate_compliance_report(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)
print(report.data_exports)      # 14
print(report.access_denials)    # 3
print(report.integrity_verified) # True
```

---

## Multi-Tenancy Setup

### Tenant Isolation Model

EL'druin uses a **shared database, separate schema** approach with row-level tenant filtering.

1. Every database table includes a `tenant_id` column.
2. All queries inject `WHERE tenant_id = :tenant_id` automatically.
3. The `AccessControlEngine.isolate_tenant_data()` method wraps raw queries.

### Provisioning a New Tenant

```bash
# Via the admin API
POST /api/v1/admin/tenants
{
  "tenant_id": "new-client",
  "name": "New Client Ltd",
  "clearance_ceiling": "confidential"
}
```

### Super-Admin Access

Users with `roles=["admin"]` and `tenant_id="system"` can access all tenant data. This capability must be restricted to infrastructure engineers only.

---

## GDPR Compliance

### Personal Data Handling

- Personal data fields (`date_of_birth`, `passport_numbers`, etc.) are classified `confidential` or higher.
- The `DataGovernanceEngine` provides anonymisation utilities (k-anonymity, pseudonymisation).
- Data retention periods are configurable per entity class.

### Right to Erasure

1. Identify all entities linked to the data subject via the KG.
2. Call `DELETE /api/v1/kg/entities/{entity_id}` for each.
3. Audit log records are retained (without PII) for compliance evidence.

### Data Portability

All entity data is exportable via `GET /api/v1/kg/entities?format=json` with appropriate clearance.

---

## SOC 2 Compliance Considerations

| Control | Implementation |
|---------|---------------|
| Access control | ABAC engine with audit trail |
| Encryption at rest | PostgreSQL/Neo4j disk encryption at infrastructure layer |
| Encryption in transit | TLS 1.2+ (enforced at load balancer / reverse proxy) |
| Audit logging | Tamper-evident hash-chained logs |
| Change management | Git-based IaC, CI/CD pipeline |
| Incident response | Audit log alerting via Kafka topic `eldruin.security` |
| Availability | Health checks, HA topology (see ARCHITECTURE.md) |

---

## Security Hardening Checklist

- [ ] Set `JWT_SECRET_KEY` to a 256-bit random value
- [ ] Set `ANONYMIZATION_SALT` to a random value
- [ ] Set `ENVIRONMENT=production` to enforce startup validation
- [ ] Enable TLS on all service-to-service and client-to-server connections
- [ ] Restrict `CORS_ORIGINS` to known frontend origins only
- [ ] Run the backend container as non-root user (UID 1001, enforced in Dockerfile)
- [ ] Enable PostgreSQL SSL: `DATABASE_URL` should include `?ssl=require`
- [ ] Rotate all secrets on a defined schedule (≤ 90 days)
- [ ] Enable network policies / security groups to restrict DB access to backend only
- [ ] Review and restrict `NEO4J_dbms_security_procedures_unrestricted` in production
