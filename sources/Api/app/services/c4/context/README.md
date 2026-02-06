# C4 Context Layer (Level 1)

This module provides a modular, maintainable approach to extracting **C4 Level 1 (System Context)** information from a codebase.

**✨ NEW:** Extracts **ALL 7 primary Service model fields** for comprehensive service metadata!

## Architecture

The context layer is organized into specialized detector classes, following the same pattern as the `containers/` module:

```
c4/context/
├── __init__.py                # Module exports
├── context_manager.py         # Main orchestrator
├── system_detector.py         # System name, purpose, languages, actors
├── dependency_detector.py     # External dependencies (databases, APIs, cloud services)
└── metadata_detector.py       # IT Landscape metadata + ALL Service model fields
```

## Complete Service Model Field Extraction

The context layer now extracts **all 7 primary fields** from the Service model:

### ✅ Primary Fields (The 7 Key Attributes)

1. **domain** - Business area (Revenue Core, Checkout, Identity, etc.)
   - Detected from: directory structure, dependencies, container names
   - Examples: "Infrastructure", "AI/ML Processing", "Data Engineering"

2. **owner** - Team/squad that owns the service
   - Detected from: CODEOWNERS, README, git contributors, LLM suggestions
   - Includes: `owner_contributors` (emails), `owner_contributor_stats` (with commit counts)

3. **status** - Lifecycle stage
   - Detected from: git commit activity
   - Values: "Active-Dev", "Maintenance-Only", "Deprecated / Frozen", "unknown"
   - Includes `status_evidence` with commit stats and dates

4. **tier** - Criticality level
   - Detected from: production indicators, SLA mentions, monitoring setup
   - Values: "Tier 1 - Production Critical", "Tier 2 - Production Standard", "Tier 3 - Development/Internal"

5. **data_class** - Sensitive data classification
   - Detected from: code scanning for sensitive keywords
   - Values: "PII", "Credit-Card", "Legal/Security", "General"

6. **active_experts** - Bus factor indicator
   - Calculated as: Contributors with 3+ commits in last 90 days
   - Higher = better (more people can maintain the service)

7. **compliance** - Architectural compliance risk
   - Assessed based on: domain, data_class, owner, tier alignment
   - Values: "COMPLIANT", "AT_RISK", "NON_COMPLIANT", "UNKNOWN"
   - Checks if sensitive data is properly prioritized and owned

### ✅ Additional Metrics

- **Git Activity Metrics:**
  - `last_commit_date` - ISO format timestamp
  - `commit_count_30d` - Commits in last 30 days
  - `commit_count_90d` - Commits in last 90 days
  - `commit_count_180d` - Commits in last 180 days
  - `contributor_count` - Total unique contributors

## Components

### ContextManager
**File:** `context_manager.py`

Main orchestrator that extracts **complete Service model metadata**. Now returns all 7 primary fields plus git metrics.

**Usage:**
```python
from app.services.c4.context import ContextManager

manager = ContextManager(repo_path, llm_manager, containers)
context = manager.extract_context()

# Access the 7 primary fields:
print(context['domain'])          # "AI/ML Processing"
print(context['owner'])            # "platform-engineering"
print(context['status'])           # "Active-Dev"
print(context['tier'])             # "Tier 2 - Production Standard"
print(context['data_class'])       # "PII"
print(context['active_experts'])   # 5
print(context['compliance'])       # "COMPLIANT"

# Access git metrics:
print(context['commit_count_90d']) # 42
print(context['last_commit_date']) # "2026-01-29T19:23:15+00:00"
```

### SystemDetector
**File:** `system_detector.py`

Detects system-level information (unchanged - see previous docs).

### DependencyDetector
**File:** `dependency_detector.py`

Detects external dependencies (unchanged - see previous docs).

### MetadataDetector
**File:** `metadata_detector.py` ⭐ **ENHANCED**

Now extracts **ALL Service model fields**:

**New Methods:**
- `detect_service_status()` → Returns (status_string, evidence_dict)
  - "Active-Dev": 5+ commits in 30 days OR 10+ in 90 days
  - "Maintenance-Only": Some activity but not actively developed
  - "Deprecated / Frozen": No commits in 180+ days

- `calculate_active_experts()` → Returns int
  - Counts contributors with 3+ commits in last 90 days
  - Bus factor indicator (higher is better)

- `assess_compliance_risk()` → Returns compliance level
  - Checks if high-risk data (PII, Credit-Card) is Tier 1/2
  - Checks if high-risk data has assigned owner
  - Checks if Tier 1 services have owners

- `get_git_activity_metrics()` → Returns complete metrics dict
  - All commit counts (30d, 90d, 180d)
  - Last commit date
  - Total contributor count

- `get_owner_contributor_stats()` → Returns detailed contributor info
  - Email list
  - Stats with commit counts per contributor
  - Contributor names (from git log)

**Existing Methods:**
- `detect_owner_team()` → str
- `infer_business_domain()` → str
- `determine_criticality()` → str
- `infer_data_classification()` → str

## Example Output

```json
{
  "c4_level": 1,
  "type": "system",
  "name": "KnowledgeForge",
  "purpose": "An ontology extraction and knowledge graph platform.",

  "// PRIMARY SERVICE FIELDS (The 7 key attributes)": "",
  "domain": "AI/ML Processing",
  "owner": "platform-engineering",
  "owner_contributors": [
    "john@company.com",
    "jane@company.com",
    "alice@company.com"
  ],
  "owner_contributor_stats": [
    {"email": "john@company.com", "name": "John Doe", "commit_count": 142},
    {"email": "jane@company.com", "name": "Jane Smith", "commit_count": 89},
    {"email": "alice@company.com", "name": "Alice Johnson", "commit_count": 56}
  ],
  "contributor_count": 8,
  "status": "Active-Dev",
  "status_evidence": {
    "commits_30d": 15,
    "commits_90d": 42,
    "commits_180d": 87,
    "last_commit_date": "2026-01-29T19:23:15+00:00",
    "days_since_last_commit": 0
  },
  "tier": "Tier 2 - Production Standard",
  "data_class": "PII",
  "active_experts": 5,
  "compliance": "COMPLIANT",

  "// GIT ACTIVITY METRICS": "",
  "last_commit_date": "2026-01-29T19:23:15+00:00",
  "commit_count_30d": 15,
  "commit_count_90d": 42,
  "commit_count_180d": 87,

  "// OTHER CONTEXT DATA": "",
  "external_dependencies": [...],
  "actors": [...],
  "languages": [...],
  "frameworks": [...]
}
```

## Status Detection Logic

**Active-Dev** (actively developed):
- 5+ commits in last 30 days, OR
- 10+ commits in last 90 days

**Maintenance-Only** (bug fixes only):
- Some commits in last 180 days
- But not meeting Active-Dev threshold

**Deprecated / Frozen** (scheduled for shutdown):
- No commits in 180+ days
- Inactive, legacy code

## 7. Compliance Risk Assessment

**NEW: 7-Check Engineering Standards Rubric**

Evaluates repository against comprehensive engineering best practices:

**The 7 Checks:**
1. ✅ **README Documentation**: README.md exists with meaningful content (>200 chars)
2. ✅ **Automated Tests**: Test files or test directories detected
3. ✅ **CI/CD Pipeline**: GitHub Actions, GitLab CI, Jenkins, or other CI config present
4. ✅ **Security Scanning**: Snyk, Dependabot, Trivy, Bandit, or security workflows configured
5. ✅ **No Hardcoded Secrets**: .env.example exists, .env not committed to git
6. ✅ **Clean Code Structure**: src/ or app/ directories, organized modules
7. ✅ **Dependency Management**: requirements.txt, package.json, go.mod, etc. present

**Scoring Thresholds:**
- **EXCELLENT** (7/7): All engineering standards met
- **COMPLIANT** (5-6/7): Minor gaps in non-critical areas
- **AT_RISK** (3-4/7): Multiple standards violations
- **NON_COMPLIANT** (0-2/7): Severe gaps OR critical security issue (e.g., .env file committed)

**Critical Security Override:**
If Check 5 fails due to .env file being committed to git, compliance is immediately
set to NON_COMPLIANT regardless of other checks (marked with 🚨).

**Implementation:**
Pure deterministic function based on file system scanning. Returns:
- `compliance_status`: "EXCELLENT", "COMPLIANT", "AT_RISK", "NON_COMPLIANT"
- `confidence`: 1.0 (deterministic checks)
- `compliance_factors`: List of passed/failed checks with score summary

**Example Output:**
```python
compliance_factors = [
    "Score: 6/7 checks passed",
    "✅ README documentation exists",
    "✅ Automated tests exist",
    "✅ CI/CD pipeline configured",
    "✅ Security scanning configured",
    "✅ No hardcoded secrets (.env.example pattern)",
    "✅ Dependency management configured",
    "❌ Poor code organization (no src/ or app/ structure)"
]
```

**Old Implementation (Deprecated):**
The previous 6-rule data-tier-ownership model has been replaced. Legacy fields
(domain, data_class, owner, tier, status, active_experts) are still passed to
maintain API compatibility but are no longer used in compliance calculation.

## Integration

The `c4_extractor.py` file uses this modular structure:

```python
from app.services.c4.context import ContextManager

class C4ArchitectureExtractor:
    def _extract_level1_context(self):
        context_manager = ContextManager(
            self.repo_path, 
            self.llm_manager, 
            self.containers
        )
        self.system_context = context_manager.extract_context()
        
        # All 7 Service model fields are now populated!
        print(self.system_context['domain'])  # "AI/ML Processing"
        print(self.system_context['status'])  # "Active-Dev"
        print(self.system_context['active_experts'])  # 5
```

## Benefits

1. **Complete Service Metadata**: All 7 Service model fields extracted automatically
2. **Bus Factor Visibility**: Active experts count shows maintenance risk
3. **Compliance Monitoring**: Automatic architectural compliance checks
4. **Lifecycle Tracking**: Service status based on actual git activity
5. **Separation of Concerns**: Each detector has a single responsibility
6. **Testability**: Easy to unit test individual detectors
7. **Maintainability**: Changes isolated to specific detectors
8. **Reusability**: Use independently or orchestrate via ContextManager

## Future Enhancements

- [ ] Add more domain detection patterns
- [ ] Enhance compliance rules (e.g., test coverage requirements)
- [ ] Support for monorepo structures (per-service metrics)
- [ ] Integration with SBOM standards
- [ ] Support for detecting service health indicators
- [ ] API contract detection and versioning
