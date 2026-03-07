# C4 Context Level Cleanup & Enhancement Plan

## Current State
The Context Level (C4 Level 1) extraction is functional but bloated with Container-level concerns and dead code.

---

## Phase 1: Remove Unnecessary Code (Cleanup) - DONE

| # | Task | Description |
|---|------|-------------|
| 1 | **Remove dead code** | Delete `canonical_models.py` - returns dicts, not using these Pydantic models |
| 2 | **Remove example code** | Delete `example_usage.py` - test/example code shouldn't be in production |
| 3 | **Remove Container fields** | Remove environment, app_version, tags, api_spec_url, monitoring_url from context output |

---

## Phase 2: Add Missing C4 Capabilities (Future)

| # | Task | Priority |
|---|------|----------|
| 4 | Add location attribute (internal/external) | High |
| 5 | Add relationship technology (REST, gRPC, etc) | High |
| 6 | Add organizational boundary grouping | Medium |
