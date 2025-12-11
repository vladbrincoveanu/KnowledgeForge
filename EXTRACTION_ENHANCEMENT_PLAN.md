# Service Extraction Enhancement Plan

## Problem Statement

Current extraction results show many missing/null values:

```json
{
  "domain": null,           // ❌ Not extracted
  "owner": null,            // ❌ Not extracted  
  "status": "unknown",      // ❌ Could be inferred from git
  "tier": "unknown",        // ⚠️ Needs config/annotations
  "data_class": null,       // ⚠️ Needs config/annotations
  "description": null,      // ❌ Could be LLM-generated
  "direct_depends": []      // ❌ Not extracted
}
```

Also, only 6 services extracted from shuup (should be more).

## Goals

| Field | Source | Implementation |
|-------|--------|----------------|
| **domain** | Imports, namespaces, package names | Parse Python/JS imports, package.json |
| **owner** | Git contributors | Top committers per service path |
| **status** | Git commit patterns | Frequency, recency, commit types |
| **tier** | Config files / annotations | Keep existing (user must annotate) |
| **data_class** | Config files / code patterns | Keep existing + scan for keywords |
| **description** | Code analysis + LLM | Sample key files → prompt LLM |
| **direct_depends** | Import analysis | Parse imports between services |

---

## Phase 1: Enhanced Git History Analyzer

### 1.1 New Module: `git_contributor_analyzer.py`

Analyzes git log to extract:

```python
@dataclass
class GitContributorStats:
    """Statistics about contributors to a service."""
    top_contributors: list[tuple[str, int]]  # (email, commit_count)
    total_commits: int
    last_commit_date: datetime
    first_commit_date: datetime
    
    # Commit type breakdown
    feature_commits: int   # "feat:", "feature", "add"
    bugfix_commits: int    # "fix:", "bug", "hotfix"
    chore_commits: int     # "chore:", "refactor", "docs"
    
    # Activity metrics
    commits_30d: int
    commits_90d: int
    commits_180d: int
```

### 1.2 Owner Extraction Logic

```python
def extract_owner(self, service_path: Path) -> tuple[str, list[str]]:
    """
    Extract owner from git contributors.
    
    Returns:
        (primary_owner, top_contributors_list)
    """
    # Run: git log --format="%ae" -- {service_path}
    # Count commits per author
    # Return top 1-3 contributors as potential owners
```

### 1.3 Enhanced Status Detection

```python
def analyze_status(self, stats: GitContributorStats) -> ServiceStatus:
    """
    Determine status from commit patterns.
    
    Rules:
    - ACTIVE_DEV: commits_30d >= 3 AND feature_commits > bugfix_commits
    - MAINTENANCE_ONLY: commits_90d > 0 AND bugfix_commits > feature_commits
    - DEPRECATED: commits_180d == 0 OR explicit deprecation keywords
    """
```

---

## Phase 2: Domain Extractor

### 2.1 New Module: `domain_extractor.py`

```python
class DomainExtractor:
    """Extract business domain from code patterns."""
    
    def extract_domain(self, service_path: Path, service_name: str) -> str:
        """
        Extract domain from multiple sources:
        
        1. Top-level namespace in imports
           - "from shuup.core.models" → domain = "core"
           - "from campaigns.api" → domain = "campaigns"
           
        2. Package.json namespace
           - "@company/checkout-service" → domain = "checkout"
           
        3. Directory structure patterns
           - "services/payments/api" → domain = "payments"
           - "apps/checkout" → domain = "checkout"
           
        4. README/docs keywords
           - Search for domain-like keywords
        """
```

### 2.2 Domain Mapping Rules

```python
DOMAIN_KEYWORDS = {
    'core': ['core', 'base', 'common', 'shared', 'utils'],
    'checkout': ['checkout', 'cart', 'basket', 'purchase'],
    'payments': ['payment', 'billing', 'invoice', 'transaction'],
    'identity': ['auth', 'user', 'account', 'identity', 'login'],
    'admin': ['admin', 'backoffice', 'management', 'cms'],
    'campaigns': ['campaign', 'promotion', 'discount', 'coupon'],
    'catalog': ['catalog', 'product', 'inventory', 'sku'],
    'shipping': ['shipping', 'delivery', 'logistics', 'fulfillment'],
    'notifications': ['notification', 'email', 'sms', 'message'],
    'analytics': ['analytics', 'metrics', 'reporting', 'stats'],
    'testing': ['test', 'e2e', 'integration', 'fixture'],
}
```

---

## Phase 3: Dependency Analyzer

### 3.1 New Module: `dependency_extractor.py`

```python
class DependencyExtractor:
    """Extract direct dependencies between services."""
    
    def __init__(self, repo_root: Path, services: list[Service]):
        self.repo_root = repo_root
        self.service_paths = {s.name: s.file_path for s in services}
        # ✅ Implemented: normalizes prefixes and resolves service paths
    
    def extract_dependencies(self, service: Service) -> list[str]:
        """
        Find which other services this one imports/depends on.
        
        Returns:
            List of service IDs that this service directly depends on
        """
        # ✅ Implemented: scans py/js/ts imports and maps to known services
```

### 3.2 Import Parsing

```python
def _parse_python_imports(self, file_path: Path) -> list[str]:
    """
    Parse Python imports to find inter-service dependencies.
    
    Example:
        from shuup.core.models import Shop
        from shuup.campaigns import Campaign
        
    Returns: ['svc-core', 'svc-campaigns']
    """
    
def _parse_js_imports(self, file_path: Path) -> list[str]:
    """
    Parse JavaScript/TypeScript imports.
    
    Example:
        import { api } from '@shuup/checkout'
        import { utils } from '../core/utils'
        
    Returns: ['svc-checkout', 'svc-core']
    """
    # ✅ Implemented: handles ES imports and require()
```

---

## Phase 4: LLM Description Generator

### 4.1 New Module: `description_generator.py`

```python
class ServiceDescriptionGenerator:
    """Generate service descriptions using local LLM."""
    
    def __init__(self, llm_manager: LLMManager):
        self.llm = llm_manager
    
    def generate_description(self, service: Service, repo_root: Path) -> str:
        """
        Generate a 1-2 sentence description of the service.
        
        Process:
        1. Find key files: README.md, __init__.py, main.py, index.ts
        2. Extract first 100-200 lines of code/docs
        3. Prompt LLM to summarize purpose
        """
```

✅ Implemented with optional LLM + heuristic fallback; wired behind `ENABLE_LLM_DESCRIPTIONS`.

### 4.2 LLM Prompt Template

```python
DESCRIPTION_PROMPT = """
Analyze this service code and provide a 1-2 sentence description.

Service: {service_name}
Path: {service_path}
Language: {language}

Key files content:
{file_contents}

Respond with ONLY a concise 1-2 sentence description of what this service does.
Focus on its business purpose, not implementation details.
"""
```

---

## Phase 5: Integration Architecture

### 5.1 Updated ServiceExtractor Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     ServiceExtractor                         │
├─────────────────────────────────────────────────────────────┤
│  1. extract_from_docker_compose()                           │
│  2. extract_from_kubernetes()                               │
│  3. extract_from_api_routes()                               │
│  4. extract_from_service_configs()                          │
│  5. extract_from_microservice_patterns()                    │
│  6. extract_from_top_level_directories()   ◄── Enhanced    │
├─────────────────────────────────────────────────────────────┤
│  NEW ENHANCEMENT PHASE (after initial extraction):          │
├─────────────────────────────────────────────────────────────┤
│  7. enhance_with_git_analysis()            ◄── Owner+Status │
│     └─ GitContributorAnalyzer                               │
│                                                              │
│  8. enhance_with_domain_detection()        ◄── Domain       │
│     └─ DomainExtractor                                      │
│                                                              │
│  9. enhance_with_dependencies()            ◄── Dependencies │
│     └─ DependencyExtractor                                  │
│                                                              │
│ 10. enhance_with_descriptions()            ◄── Description  │
│     └─ ServiceDescriptionGenerator (optional, feature flag) │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Feature Flags

```python
# In extraction_config.py

class ExtractionConfig:
    # Storage
    STORE_TO_JSON: bool = True
    STORE_TO_NEO4J: bool = False
    
    # Enhancement features
    ENABLE_GIT_ANALYSIS: bool = True      # Owner + Status from git
    ENABLE_DOMAIN_DETECTION: bool = True  # Domain from imports
    ENABLE_DEPENDENCY_SCAN: bool = True   # Direct dependencies
    ENABLE_LLM_DESCRIPTIONS: bool = False # LLM descriptions (slower)
    
    # Git settings
    GIT_CLONE_FOR_ANALYSIS: bool = True   # Clone with git for full history
    GIT_CONTRIBUTOR_LIMIT: int = 5        # Max contributors to track
    
    # LLM settings
    LLM_MAX_TOKENS: int = 150
    LLM_DESCRIPTION_ENABLED: bool = False  # Off by default (slow)
```

---

## Phase 6: Updated JSON Output

### 6.1 Enhanced services.json Structure

```json
{
  "services": [
    {
      "id": "svc-campaigns",
      "name": "campaigns",
      "display_name": "Campaigns",
      
      "domain": "marketing",
      "owner": "team-growth@company.com",
      "owner_contributors": [
        "john@company.com",
        "jane@company.com"
      ],
      "status": "Active-Dev",
      "status_evidence": {
        "commits_30d": 15,
        "commits_90d": 42,
        "feature_ratio": 0.6,
        "last_commit": "2024-12-01"
      },
      "tier": "Tier 2",
      "data_class": null,
      
      "description": "Manages marketing campaigns, discounts, and promotional offers for the e-commerce platform.",
      
      "direct_depends": ["svc-core", "svc-products"],
      
      "language": "Python",
      "framework": "Django",
      "file_path": "shuup/campaigns",
      "source": "top_level_directory",
      
      "last_commit_date": "2024-12-01T14:30:00Z",
      "commit_count_30d": 15,
      "commit_count_90d": 42,
      "commit_count_180d": 78,
      
      "confidence": 0.85
    }
  ]
}
```

---

## Implementation Order

| Priority | Task | Complexity | Impact |
|----------|------|------------|--------|
| 1 | Git Contributor Analyzer (owner) | Medium | High |
| 2 | Enhanced Git Status Analysis | Low | High |
| 3 | Domain Extractor | Medium | High |
| 4 | Dependency Extractor | Medium | High |
| 5 | LLM Description Generator | Low | Medium |
| 6 | Update JSON output | Low | Medium |
| 7 | Integration + Testing | Medium | High |

---

## File Changes Summary

### New Files:
- `app/services/service_extraction/git_contributor_analyzer.py`
- `app/services/service_extraction/domain_extractor.py`
- `app/services/service_extraction/dependency_extractor.py`
- `app/services/service_extraction/description_generator.py`

### Modified Files:
- `app/services/service_extraction/service_extractor.py` - Add enhancement phase
- `app/services/service_extraction/extraction_config.py` - Add feature flags
- `app/services/service_extraction/git_status_analyzer.py` - Enhance with commit types
- `app/endpoint/v1/routes/service_extraction.py` - Update JSON output
- `app/domain/models/services.py` - Already has needed fields

---

## Next Steps

1. ✅ **Phase 1** - Git Contributor Analyzer (owner/status from git)
2. ✅ **Phase 2** - Domain Extractor (imports/namespaces)
3. ✅ **Phase 3** - Dependency Extractor (direct_depends via imports)
4. ✅ **Phase 4** - LLM Descriptions (optional, feature-flagged)
5. ✅ **Phase 5 & 6** - Integration & JSON Output - Validated end-to-end

**Status**: ✅ All phases completed and validated via integration tests.
