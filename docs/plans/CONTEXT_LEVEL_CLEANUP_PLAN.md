# C4 Context Level Cleanup & Enhancement Plan

## Current State
The Context Level (C4 Level 1) extraction is functional but bloated with Container-level concerns and dead code.

---

## Phase 1: Remove Unnecessary Code (Cleanup)

| # | Task | Description | Files |
|---|------|-------------|-------|
| 1 | **Remove dead code** | Delete `canonical_models.py` - returns dicts, not using these Pydantic models | `c4/context/canonical_models.py` |
| 2 | **Remove example code** | Delete `example_usage.py` - test/example code shouldn't be in production | `c4/context/example_usage.py` |
| 3 | **Remove bloat from system_detector** | Remove Container-level fields: `app_version`, `tags`, `environment`, `api_spec_url`, `monitoring_url` | `c4/context/system_detector.py` |
| 4 | **Remove redundant classifier** | Check if `dependency_classifier.py` is redundant with `dependency_detector.py` | `c4/context/dependency_classifier.py` |

---

## Phase 2: Fix Context/Container Leakage

| # | Task | Description | Files |
|---|------|-------------|-------|
| 5 | **Remove deployment fields from Context** | Fields like `app_version`, `tags`, `environment` are Container-level - remove from context extraction | `c4/context/context_manager.py` |
| 6 | **Simplify metadata_detector** | Remove DORA metrics, compliance risk, bus factor calculations - move to Container level | `c4/context/metadata_detector.py` |

---

## Phase 3: Add Missing C4 Capabilities

| # | Task | Description | Priority |
|---|------|-------------|----------|
| 7 | **Add location attribute** | Tag system and actors as `internal` / `external` / `internet` | High |
| 8 | **Add relationship technology** | Capture protocol (REST, gRPC, Kafka, JDBC) on relationships | High |
| 9 | **Add organizational boundary** | Group entities by boundary (e.g., "Within Org", "External Partners") | Medium |
| 10 | **Add security boundary detection** | Detect DMZ, API gateway, VPN boundaries | Low |

---

## Target: Minimal Context Extractor

After cleanup, Context extraction should return ~12 core fields:

```
{
  "name": "PaymentService",
  "purpose": "Processes customer payments",
  "location": "internal",           # NEW
  "owner": "platform-core",
  "domain": "Payments",
  "status": "ACTIVE",
  "tier": "Tier 1",
  "languages": [...],
  "frameworks": [...],
  "external_dependencies": [...],
  "relationships": [                # NEW - enhanced
    {"source": "User", "target": "PaymentService", "type": "uses", "tech": "HTTPS"},
    {"source": "PaymentService", "target": "Stripe", "type": "uses", "tech": "REST API"}
  ]
}
```

---

## Implementation Order

1. Tasks 1-4: Remove dead code (low risk)
2. Tasks 5-6: Fix leakage (medium risk - need to verify tests)
3. Tasks 7-10: Add missing capabilities (new features)
