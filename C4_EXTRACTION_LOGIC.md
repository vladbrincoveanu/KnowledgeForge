# C4 Architecture Extraction - Quick Reference

## Overview
Automated extraction of C4 architecture from GitHub repositories analyzing code structure, Git history, configs, and documentation.

---

## 📊 Extraction Pipeline

```
GitHub Repository → Clone (full history) → Parse Files → Pattern Matching → JSON → UI
```

**Sources:** CODEOWNERS, README.md, values.yaml, .env, docker-compose.yml, Git history, Kubernetes configs

---

## 🛠️ Maintenance & Regression
To ensure the extraction logic stays accurate across changes:
- **`make quick-check`**: Restarts the API and runs 11 E2E extraction tests.
- **`make full-check`**: Rebuilds the entire stack from scratch and runs all tests.
- **`make test-e2e`**: Runs the standalone regression suite.

All tests must pass (11/11) before committing extraction changes.

---

## 🎯 Context Level - System Metadata

### 1. Domain 🏢
**Business area** → Repo name, README patterns → Default: `Infrastructure`

### 2. Owner Team 👥
**Responsible team** → CODEOWNERS → README → Git contributors (email domains) → **Needs full history**

### 3. Lifecycle Status 🔄
**Software stage** → README badges + Last commit: <6mo=Active, 6-18mo=Maintenance, >36mo=Deprecated

### 4. Criticality Tier ⚡
**Business impact** → README keywords + `/prod/`=Tier1, `/staging/`=Tier2, `/dev/`=Tier3

### 5. Data Sensitivity 🔒
**Data class** → Pattern match: password/email/ssn/GDPR → PII or Internal

### 6. Active Experts (Bus Factor) 🚌
**Knowledge concentration** → Git analysis: Top contributor >70%=1 (risk), Distributed=3+

### 7. Architectural Compliance ✅
**Standards adherence** → Checklist: README+tests+CI+docs+no-secrets → COMPLIANT/AT_RISK/NON_COMPLIANT

### 8. External Dependencies 🔗
**Third-party services** → values.yaml, .env, docker-compose, README → Extract URLs + infer type (Stripe=payment, AWS=cloud)

---

## 🔍 Container Level - Microservices

### Detection Patterns
- **Kubernetes:** `deployments/*.yaml`, `services/*.yaml`
- **Helm:** `Chart.yaml` + `templates/` directory
- **Docker Compose:** `docker-compose.yml`
- **Directory:** `/services/`, `/apps/`, `/microservices/`

### Per Container Extracted
- **Name** → File/folder name
- **Type** → API, Database, UI, Queue, Cache
- **Service URL** → values.yaml `ingress.host` or ingress.yaml `spec.rules[].host`
- **Endpoint** → values.yaml `ingress.path` or ingress.yaml paths
- **Dependencies** → Service links and references

---

## 🧪 Testing

```bash
make test-e2e          # All 11 tests
make test-owner        # Owner detection
make test-containers   # Container detection
make test-endpoints    # Endpoint extraction
```

**Status:** 11/11 passing ✅

---

## 📂 Source Code

| File | Purpose |
|------|---------|
| `github_downloader.py` | Clone repos (full history) |
| `metadata_detector.py` | IT landscape fields |
| `dependency_detector.py` | External services |
| `structure_detector.py` | Container detection |
| `utils.py` | Endpoint extraction |

---

## 🎨 UI Mapping

| JSON | UI Label |
|------|----------|
| domain | Domain |
| owner | Owner Team |
| status | Lifecycle Status |
| tier | Criticality Tier |
| data_class | Data Sensitivity |
| active_experts | Active Experts (Bus Factor) |
| compliance | Architectural Compliance |
| url | Service URL |
| endpoint | Access Endpoint |
| attributes.url | External Service URL (clickable) |

---

## 📖 Detailed Guides

- **Context Level:** `CONTEXT_EXTRACTION_GUIDE.md`
- **UI & Testing:** `UI_FIXES_AND_TESTING_SUMMARY.md`
