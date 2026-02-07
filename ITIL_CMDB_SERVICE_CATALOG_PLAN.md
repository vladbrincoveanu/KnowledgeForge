# ITIL CMDB & Service Catalog Compliance Plan

**Status:** In Progress  
**Start Date:** 2026-02-07  
**Goal:** Increase ITIL Configuration Management Database (CMDB) and Service Catalog coverage from ~40% to 75%+ by adding missing CI attributes and service metadata fields.

---

## Executive Summary

KnowledgeForge's C4 architecture extraction already captures core CMDB CI attributes:
- ✅ CI Name, ID, Type, Status, Owner, Business Criticality (Tier 1/2/3), Data Classification
- ✅ Partial: Dependencies, Relationships, Lifecycle State, Last Change

**Key Gaps:**
- ❌ Environment classification (dev/staging/prod)
- ❌ Application version (distinct from runtime version)
- ❌ SLA targets, monitoring URLs, API documentation links
- ❌ Service catalog fields: runbooks, on-call channels, cost centers
- ⚠️ Container data is untyped dictionaries (not Pydantic models)

---

## Current State Analysis

### Covered CMDB CI Attributes (40% coverage)
| CMDB Field | KnowledgeForge Field | Source |
|---|---|---|
| CI Name | `name`, `display_name` | SystemContext, Container dict |
| CI ID | `id` | Deterministic hash |
| CI Type | `container_type`, `entity_type` | Detector classification |
| CI Status | `lifecycle_status` | Git activity analysis |
| Owner | `owner`, `git_contributors` | Git history, CODEOWNERS |
| Business Criticality | `tier` | Dependency analysis |
| Data Classification | `data_sensitivity` | Code/config pattern detection |
| Last Change | `last_commit_date` | Git metadata |
| Dependencies | `dependencies_internal`, `external_dependencies` | Import/config analysis |

### Covered Service Catalog Attributes (35% coverage)
| Catalog Field | KnowledgeForge Field | Source |
|---|---|---|
| Service Name | `name`, `display_name` | Container dict |
| Service Description | `description`, `purpose` | README, LLM enrichment |
| Business Domain | `domain` | Path/owner inference |
| Service Owner | `owner` | Git contributors |
| Service Tier | `tier` | Tier 1/2/3 classification |
| Data Classification | `data_sensitivity` | PII/credit-card detection |
| Protocol | `protocol` | REST, gRPC, GraphQL |
| Dependencies | `dependencies_internal` | All detectors |

### Missing Critical Fields
- Environment (dev/staging/prod)
- App version (vs runtime version)
- API documentation URLs
- Runbook/wiki links
- Monitoring dashboard URLs
- On-call channels
- SLA targets
- Tags/labels
- Cost center
- Resource limits/replicas
- Regional deployment info

---

## Implementation Phases

### Phase 1: Foundation & Quick Wins (Priority: HIGH)
**Timeline:** Week 1  
**Goal:** Add immediately detectable fields with high business value

#### 1.1 Create Typed Container Pydantic Model
- **Task:** Replace untyped dictionaries with `Container` model in `models.py`
- **Benefits:** Type safety, validation, self-documenting schema
- **Files:** `sources/Api/app/models.py`

#### 1.2 Add Core CMDB Fields
| Field | Type | Detectable From | Extractor |
|---|---|---|---|
| `environment` | `List[str]` | Helm `values-{env}.yaml`, namespace labels, branch | All detectors |
| `app_version` | `str` | Chart.yaml `appVersion`, package.json `version` | HelmDetector, StructureDetector |
| `tags` | `Dict[str, str]` | K8s labels, Helm labels, GitHub topics | HelmDetector |

#### 1.3 Add Service Catalog URLs
| Field | Type | Detectable From | Extractor |
|---|---|---|---|
| `api_spec_url` | `Optional[str]` | `/docs`, `/swagger.json`, `/openapi.yaml` endpoints | Component-level scan |
| `documentation_url` | `Optional[str]` | README links (wiki, Confluence, Notion) | README parser |
| `monitoring_url` | `Optional[str]` | Grafana annotations in Helm, README sections | HelmDetector, README parser |

#### 1.4 Populate Downstream Dependencies
- **Task:** Reverse-index `dependencies_internal` to fill `downstream_dependencies`
- **Files:** `sources/Api/app/services/c4/merge_and_link.py` or new `dependency_resolver.py`

### Phase 2: Advanced Detection (Priority: MEDIUM)
**Timeline:** Week 2-3  
**Goal:** Add fields requiring deeper code/config analysis

#### 2.1 Operational Fields
| Field | Type | Detectable From |
|---|---|---|
| `on_call_channel` | `Optional[str]` | CODEOWNERS, README contact sections, PagerDuty annotations |
| `sla_target` | `Optional[float]` | SLA docs, Helm annotations, README uptime badges |
| `replica_count` | `Optional[int]` | Helm values, K8s Deployment manifests |
| `resource_limits` | `Dict[str, str]` | Helm values (CPU/memory limits) |

#### 2.2 Infrastructure Fields
| Field | Type | Detectable From |
|---|---|---|
| `region` | `Optional[str]` | K8s node labels, Terraform `region`, Helm values |
| `availability_zone` | `Optional[str]` | K8s node labels, cloud provider metadata |
| `deployment_strategy` | `Optional[str]` | Helm/K8s strategy (RollingUpdate, Recreate) |

#### 2.3 Security & Compliance
| Field | Type | Detectable From |
|---|---|---|
| `security_scan_status` | `Optional[str]` | CI pipeline config (GitHub Actions scanning steps) |
| `regulatory_frameworks` | `List[str]` | README badges, COMPLIANCE.md (SOC2, GDPR, HIPAA) |
| `authentication_method` | `Optional[str]` | Middleware detection (OAuth, JWT, API key) |

#### 2.4 Enhance Compliance Assessment
- Extend `compliance_status` to include regulatory frameworks (SOC2, GDPR, HIPAA)
- Add detection for policy-as-code files (OPA, Kyverno)
- Files: `sources/Api/app/services/c4/enrichment/compliance_assessor.py`

### Phase 3: Integration & Advanced Metrics (Priority: LOW)
**Timeline:** Week 4+  
**Goal:** External system integration and computed metrics

#### 3.1 Cost & Financial
- `cost_center`: K8s namespace labels, Terraform tags
- `cloud_spend`: Integration with AWS Cost Explorer, Azure Cost Management

#### 3.2 Observability
- `log_aggregation_url`: Splunk/ELK links from K8s annotations
- `tracing_url`: Jaeger/Zipkin links

#### 3.3 DORA Metrics
- `deployment_frequency`: CI/CD pipeline history
- `lead_time_for_changes`: Git commit to deploy time
- `mttr`: Incident history from PagerDuty/Jira
- `change_failure_rate`: Failed deployments from CI/CD

#### 3.4 Dependency Management
- `dependency_freshness`: Compare package versions to latest
- `vulnerability_count`: Integration with Snyk/Dependabot

---

## Technical Implementation Details

### New Pydantic Model: `Container`

**Location:** `sources/Api/app/models.py`

```python
class Container(BaseModel):
    """
    ITIL CMDB-compliant Container CI model (C4 Level 2).
    Replaces untyped dictionaries with validated schema.
    """
    # Core Identity (existing)
    id: str
    name: str
    display_name: Optional[str] = None
    container_type: str
    description: Optional[str] = None
    
    # Phase 1: New CMDB Fields
    environment: List[str] = Field(default_factory=list, description="Deployment environments: dev, staging, prod")
    app_version: Optional[str] = Field(None, description="Application version (Chart.yaml appVersion, package.json version)")
    tags: Dict[str, str] = Field(default_factory=dict, description="Freeform labels from K8s/Helm/GitHub")
    
    # Phase 1: Service Catalog URLs
    api_spec_url: Optional[str] = Field(None, description="OpenAPI/Swagger documentation URL")
    documentation_url: Optional[str] = Field(None, description="Wiki/runbook/README URL")
    monitoring_url: Optional[str] = Field(None, description="Grafana/Datadog dashboard URL")
    
    # Existing fields (from current container dicts)
    technology: Optional[str] = None
    protocol: Optional[str] = None
    path: Optional[str] = None
    dependencies_internal: List[str] = Field(default_factory=list)
    downstream_dependencies: List[str] = Field(default_factory=list)  # Phase 1: populate this
    external_dependencies: List[str] = Field(default_factory=list)
    
    # Runtime & Infrastructure
    runtime_info: Optional[str] = None
    orchestration: Optional[str] = None
    deployment_mechanism: Optional[str] = None
    
    # Observability
    health_endpoint: Optional[str] = None
    endpoint: Optional[str] = None
    
    # Metadata
    repo_url: Optional[str] = None
    components: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Phase 2 fields (commented for future)
    # on_call_channel: Optional[str] = None
    # sla_target: Optional[float] = None
    # replica_count: Optional[int] = None
    # resource_limits: Optional[Dict[str, str]] = None
    # region: Optional[str] = None
```

### Extractor Changes

#### HelmDetector (`helm_detector.py`)
- Extract `environment` from values file naming patterns (`values-prod.yaml`)
- Extract `app_version` from `Chart.yaml` `appVersion` field
- Extract `tags` from Helm chart labels
- Extract `monitoring_url` from Grafana annotations in values

#### StructureDetector (`structure_detector.py`)
- Extract `app_version` from `package.json` `version`, `pyproject.toml` `version`
- Extract `documentation_url` from README link sections
- Detect `api_spec_url` by scanning for `/docs`, `/swagger`, `/openapi` route definitions

#### SystemContextDetector (`system_context_detector.py`)
- Add same Phase 1 fields to `SystemContext` model
- Extract regulatory frameworks from README badges (SOC2, GDPR, HIPAA)

#### Merge & Link Phase
- **New utility:** `dependency_resolver.py` to reverse-index dependencies
- Populate `downstream_dependencies` for all containers
- Validate bidirectional dependency links

---

## Testing Strategy

### E2E Test Updates
- **File:** `sources/Api/test_e2e_extraction.py`
- **Goal:** Ensure 11/11 tests still pass after each phase

**New Assertions:**
```python
# Phase 1 validation
assert "environment" in container
assert container.get("app_version") is not None
assert isinstance(container.get("tags"), dict)
assert container.get("downstream_dependencies") is not None
```

### Unit Tests
- `test_container_model.py` — Validate Pydantic schema
- `test_version_extraction.py` — Test `app_version` detection
- `test_url_extraction.py` — Test API spec/doc URL detection
- `test_dependency_resolver.py` — Test downstream dep population

---

## Validation & Rollout

### Phase 1 Acceptance Criteria
- [ ] `Container` Pydantic model created and used in all detectors
- [ ] `environment`, `app_version`, `tags` extracted for ≥70% of containers
- [ ] `api_spec_url`, `documentation_url` extracted for ≥50% of containers
- [ ] `downstream_dependencies` populated for all containers with dependents
- [ ] All 11 E2E tests pass
- [ ] `make quick-check` succeeds

### Phase 2 Acceptance Criteria
- [ ] `on_call_channel`, `sla_target` extracted for ≥30% of containers
- [ ] `resource_limits`, `replica_count` extracted for K8s-deployed services
- [ ] `security_scan_status` integrated from CI pipeline configs
- [ ] Compliance assessment includes regulatory frameworks

### Phase 3 Acceptance Criteria
- [ ] External integration points defined (APIs for PagerDuty, Jira, AWS Cost Explorer)
- [ ] DORA metrics calculated for ≥50% of services
- [ ] Dependency freshness alerts generated

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Breaking existing extraction | Incremental rollout, all new fields Optional, maintain backward compat |
| E2E test failures | Test after each change, use `make quick-check` |
| Performance degradation | Profile extractors, cache expensive operations, async where possible |
| False positives in URL detection | Strict regex patterns, validation heuristics |
| Missing data in mono-repos | Fallback to repo-level defaults, allow manual overrides |

---

## Future Enhancements

### CMDB Integration Webhooks
- POST container updates to external CMDBs (ServiceNow, Jira Assets)
- Webhook payload: JSON-serialized `Container` model

### Service Catalog UI
- Render ITIL-compliant service catalog view in React UI
- Filter by environment, tier, compliance status
- Export to CSV/Excel for CMDB import

### Automated SLA Monitoring
- Periodically check `health_endpoint` uptime
- Compare against `sla_target`, flag violations

### Cost Attribution
- Integrate with FinOps tools (Kubecost, CloudHealth)
- Associate `cost_center` with actual cloud spend

---

## References

- **ITIL 4 CMDB Best Practices:** [https://www.axelos.com/certifications/itil-service-management](https://www.axelos.com/certifications/itil-service-management)
- **C4 Model Specification:** [https://c4model.com](https://c4model.com)
- **KnowledgeForge Docs:**
  - `CONTEXT_EXTRACTION_GUIDE.md`
  - `C4_EXTRACTION_LOGIC.md`
  - `REFACTORING_MASTER_PLAN.md`
  - `MOTHER_COMMANDS.md`

---

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-02-07 | Initial plan created | GitHub Copilot |
| TBD | Phase 1 implementation complete | - |
