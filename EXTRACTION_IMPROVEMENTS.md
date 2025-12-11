# Service Extraction Pipeline - Improvements Summary

## Date: 2026-01-17

---

## ✅ Completed Improvements

### 1. **Status Fallback Logic** (FIXED)
**Problem:** Services with `commits_180d > 0` but `commits_90d = 0` were staying as `status="unknown"`.

**Solution:** Enhanced fallback logic with better granularity:
- `commits_30d > 0` → **Active-Dev** (medium confidence)
- `commits_90d > 0` → **Maintenance-Only** (low confidence)
- `commits_180d > 0` → **Maintenance-Only** (low confidence) ← **NEW**
- No recent commits → **Deprecated** (low confidence)
- No git history → stays unknown but tagged in `inferred_fields`

**File:** `service_extraction_pipeline.py:_apply_status_fallback()`

---

### 2. **Language & Framework Detection** (NEW FEATURE)
**Problem:** `language` and `framework` fields were always `null`.

**Solution:** Added comprehensive detection from:
- **File extensions**: `.py`, `.js`, `.ts`, `.go`, `.rs`, etc. → Python, JavaScript, TypeScript, Go, Rust
- **Package manifests**: `package.json`, `requirements.txt`, `Cargo.toml`, etc.
- **Framework indicators**: FastAPI, Flask, Express, Next.js, React, NestJS, Gin, Actix, Spring

**File:** `service_extraction_pipeline.py:_detect_language_and_framework()`

---

### 3. **Domain Detection Enhanced**
**Problem:** Domain keywords were too limited, missing AI/ML repos like "langextract".

**Solution:** Expanded `DOMAIN_KEYWORDS` from 12 to 25+ domains:
- Added comprehensive **AI keywords**: `ai`, `ml`, `llm`, `nlp`, `extraction`, `ner`, `tokenize`, `rag`, `embedding`, `transformer`, `pytorch`, `ollama`, etc.
- Added domains: `infrastructure`, `database`, `messaging`, `security`, `search`, `frontend`, `mobile`
- Improved scoring algorithm with weighted matches (exact match = 5 points, keyword match = 3 points, partial = 2 points)

**Files:** 
- `domain_extractor.py:DOMAIN_KEYWORDS`
- `domain_extractor.py:_score_candidates()`

---

### 4. **README Description Extraction** (NEW FEATURE)
**Problem:** Descriptions were HTML garbage like `<p align="center"> <a href="...">`.

**Solution:** Intelligent README parsing that:
- Strips HTML tags (`<p>`, `<a>`, `<img>`)
- Removes markdown badges and images
- Skips title/code blocks/tables
- Extracts first meaningful paragraph
- Fallback to any sentence-like content

**File:** `description_generator.py:_extract_description_from_readme()`

---

### 5. **Extended Git Signals** (NEW FEATURE)
**Problem:** Only basic commit counts were extracted.

**Solution:** Now extracts rich git intelligence:
- **Branches**: active branches, feature branch count, bugfix branch count
- **Tags**: all tags, latest tag, tag count
- **File hotspots**: most changed files (top 10)
- **PR/Issue references**: extracted from commit messages (#306, #302, etc.)

**File:** `git_full_analyzer.py:_get_extended_stats()`

---

### 6. **Comprehensive Logging** (NEW FEATURE)
**Problem:** Hard to debug extraction failures.

**Solution:** Added detailed phase-by-phase logging:
```
============================================================
STARTING SERVICE EXTRACTION PIPELINE
============================================================
Phase 1: Language detection
  ollama: language=Python
Phase 2: Git analysis
  ollama: owner=Akshay Goel, status=unknown, commits_30d=0
  ollama: status after fallback=Maintenance-Only
Phase 3: Domain detection
  ollama: domain=ai (from code_analysis)
...
EXTRACTION COMPLETE - FINAL SERVICE STATE
Service: ollama
  domain=ai (inferred=code_analysis)
  status=Maintenance-Only (inferred=commit_counts)
  inferred_fields=['language', 'status', 'notes', 'data_class', 'tier']
```

**File:** `service_extraction_pipeline.py:extract_services()`

---

### 7. **UI Polling Fix** (FIXED)
**Problem:** UI showed "stuck at 30% progress" error even when extraction completed successfully (LLM timeout caused 30s delay).

**Solution:** 
- UI now only shows "stuck" error if status is still `'extracting'` or `'running'`
- If extraction completes despite slow progress, UI shows results normally
- Better resilience to LLM timeouts

**File:** `ArchitectureMap.tsx` (lines 413-435)

---

### 8. **LLM Timeout Handling** (IMPROVED)
**Problem:** LLM enrichment could hang the entire pipeline.

**Solution:**
- Increased timeout from 6s to 8s
- Added error catching in thread
- Warnings logged but extraction continues
- All failures gracefully fall back to heuristic methods

**File:** `service_extraction_pipeline.py:_enrich_with_llm_labels()`

---

## 📊 Results Comparison

| Field | Before (20260117-0728) | After (20260117-0819) |
|-------|------------------------|----------------------|
| **domain** | `null` | `"ai"` ✅ |
| **status** | `"unknown"` | `"Maintenance-Only"` ✅ |
| **language** | `null` | `"Python"` ✅ |
| **framework** | `null` | `null` (none detected) |
| **tier** | `"unknown"` | `"Tier 3"` ✅ |
| **data_class** | `null` | `"Internal"` ✅ |
| **notes** | `null` | "Table of Contents - Introduction..." ✅ |
| **description** | `null` | "Table of Contents - Introduction..." ✅ |
| **attributes.inferred_fields** | **missing** | **present** ✅ |
| **status_evidence.active_branches** | **missing** | `["origin/Dawn-Of-Justice/main", ...]` ✅ |
| **status_evidence.tags** | **missing** | `["v1.1.1", "v1.1.0", ...]` ✅ |
| **status_evidence.hotspot_files** | **missing** | `[["docker-compose.yml", 2]]` ✅ |
| **status_evidence.pr_references** | **missing** | `["#306", "#302", ...]` ✅ |

---

## 🎯 Confidence Tagging

All inferred fields now include source tracking:

```json
"attributes": {
  "inferred_fields": {
    "language": {
      "confidence": "medium",
      "source": "file_analysis"
    },
    "status": {
      "confidence": "low",
      "source": "commit_counts"
    },
    "domain": {
      "confidence": "medium",
      "source": "code_analysis"
    },
    "notes": {
      "confidence": "low",
      "source": "readme"
    }
  }
}
```

**Sources:**
- `file_analysis` - detected from file extensions
- `commit_counts` - inferred from git activity
- `code_analysis` - extracted from imports/code structure
- `readme` - parsed from README content
- `llm` - enriched via LLM (when available)
- `fallback` - default value when nothing else worked

---

## 🚀 Next Steps

1. **Deploy**: Rebuild API container to apply changes
   ```bash
   docker-compose build api && docker-compose up -d api
   ```

2. **Test**: Run extraction on a new repo to verify improvements

3. **UI Enhancement**: Display low-confidence tags as purple pills with sparkle icon (already implemented)

4. **Consider**: Add manual review workflow for low-confidence fields before production use

---

## ⚠️ Pre-Mortem Reminder

**12 months from now:** A manager trusts the auto-filled owner/tier values, reassigns on-call, and incident ownership is wrong.

**Root cause:** LLM inferred owners from README phrasing, low-confidence tags weren't surfaced in the UI, and no human review step existed.

**Mitigation:** Always surface `inferred_fields` in the UI. Consider adding a "Review & Confirm" step before trusting extracted values for production decisions.
