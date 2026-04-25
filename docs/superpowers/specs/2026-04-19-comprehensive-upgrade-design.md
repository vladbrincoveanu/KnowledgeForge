# KnowledgeForge Comprehensive Upgrade — Design Spec

**Date:** 2026-04-19
**Status:** Draft
**Type:** Multi-stream upgrade (tests, edge cases, UI, skill integration)

---

## 1. Overview

Upgrade KnowledgeForge across 4 areas:
1. **Integration Tests** — Comprehensive harness using existing OmniPay demo repos
2. **Edge Case Functionality** — Fill extraction gaps (Rust detection, symlink handling)
3. **UI Professionalization** — Enterprise Dashboard refinement of the React frontend
4. **Skill Integration** — Hard-rule auto-invoke of ui-ux-pro-max for UI work

**Parallel streams:** Backend (tests + edge cases) and UI run concurrently. Skill integration is independent.

---

## 2. Stream A — Integration Test Suite

### 2A-1: Shared Test Harness (`tests/harness/`)

A pytest fixture library that provides deterministic extraction runs against OmniPay demo repos.

**Module:** `tests/harness/omnipay_harness.py`

- **Responsibility:** Boots OmniPay demo repos, runs extraction pipeline, returns structured results
- **Interface:**
  - `omnipay_repo(repo_name: str) -> Path` — returns path to demo repo, inits git if needed
  - `extract_containers(repo_path: Path) -> List[dict]` — runs StructureDetector, returns container dicts
  - `extract_context(repo_path: Path) -> dict` — runs ContextManager, returns system context
- **Dependencies:** `StructureDetector`, `ContextManager`, `ContainerManager`, `GitHubDownloader`
- **Size target:** ~150 lines, 3 fixtures

**Module:** `tests/harness/fixtures.py`

- **Responsibility:** Deterministic LLM double for container enrichment
- **Interface:** `FakeOmniPayLLM` class — returns preset JSON for "billing-llm" and "ml-pipeline" containers
- **Dependencies:** None (pure double)
- **Size target:** ~60 lines

### 2A-2: Test Organization

```
tests/
  harness/
    __init__.py
    omnipay_harness.py      # Shared fixtures
    fixtures.py             # LLM doubles, factory functions
  e2e/
    test_omnipay_extraction.py    # Existing — keep as-is
    test_omnipay_harness.py       # NEW — harness-driven tests
    test_edge_cases.py             # NEW — edge case coverage
    snapshots/
      omnipay_extraction.json      # Existing snapshot
  unit/
    # existing tests unchanged
```

### 2A-3: New Test Files

**`tests/e2e/test_omnipay_harness.py`**

- Uses shared harness fixtures
- Tests 6 core services: ledger (Java), fraud-ml (Python), gateway (TS), notifier (Go), card-router (C#), infra (Terraform)
- Per-service: language detection, technology field, container type, ownership
- Assertions: exact field presence, type correctness, no "Unknown" defaults in core fields

**`tests/e2e/test_edge_cases.py`** — covers 5 edge case scenarios:

| Test | Source | What it validates |
|------|--------|-------------------|
| `test_rust_detection` | `omnipay-rust-service` | Rust language + Cargo.toml detection |
| `test_symlink_handling` | `omnipay-symlink-service` | Symlink resolution, no duplicate containers |
| `test_multi_lang_tiering` | `omnipay-multi-lang` | Correct tier assignment for polyglot repos |
| `test_conflicted_ownership` | `omnipay-conflicted-ownership` | CODEOWNERS conflict → both owners recorded |
| `test_no_ownership_graceful` | `omnipay-no-ownership` | No CODEOWNERS/README → owner="Unassigned" |

**`tests/e2e/test_provider_catalog.py`** — covers dictionary matching:

- Stripe, Mixpanel, Auth0, PostgreSQL, Redis, MongoDB, Kafka, RabbitMQ, SQL Server
- Package name matching, env var matching, detection_source correctness
- External dependency structure (name, provider, detected_from_all)

**`tests/e2e/test_llm_enrichment.py`** — covers LLM adjudication:

- DecisionMode enum values
- ExtractionDecision.to_dict() structure
- omnipay-billing-llm and omnipay-ml-pipeline receive llm_enriched=True with correct verdict/confidence/notes

**`tests/e2e/test_snapshot_regression.py`** — regression detection:

- Loads `snapshots/omnipay_extraction.json`
- Compares container count, service names, key field values
- Fails on drift — regenerate with `--snapshot-update`

### 2A-4: Test Execution

```bash
# Run all E2E
make test-e2e-omnipay

# Run edge cases only
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py -v

# Update snapshot
docker compose exec api python -m pytest tests/e2e/test_snapshot_regression.py -v --snapshot-update
```

---

## 3. Stream B — Edge Case Functionality

### 3B-1: Rust Detection

**Module:** `app/services/c4/containers/python_library_detector.py` (or new `rust_detector.py`)

- **Responsibility:** Detect Rust services via `Cargo.toml` and `.rs` source files
- **Interface:** Similar pattern to existing language detectors
- **Detection signals:**
  - `Cargo.toml` at repo root or any subdirectory → Rust service
  - `.rs` files alongside `Cargo.toml` confirms compiled Rust
  - Container type: "Rust Service", technology: "Rust"

### 3B-2: Symlink Handling

**Module:** `app/services/c4/containers/structure_detector.py` (patch)

- **Responsibility:** Resolve symlinks before creating containers; deduplicate
- **Interface:** Patch existing `detect()` method
- **Detection signals:**
  - Skip creating a container for a symlink path that points to an already-detected service
  - Flag symlinks in container metadata (`is_symlink: true`, `symlink_target: str`)
- **Test:** `omnipay-symlink-service` — structure should not double-count

### 3B-3: Multi-language Repo Tiering

**Module:** `app/services/c4/context/metadata_detector.py` (patch to `detect_tier`)

- **Responsibility:** For polyglot repos, assign tier based on highest-criticality language
- **Interface:** Patch `detect_tier()` to consider all detected languages
- **Rule:** If any language is "Tier 1" (e.g., Java, TypeScript in payment domain), assign Tier 1
- **Test:** `omnipay-multi-lang` — tier should reflect most critical component

---

## 4. Stream C — UI Professionalization (Enterprise Dashboard)

### 4C-1: Design Direction

**Style:** Enterprise Dashboard — information-dense, structured, muted palette, strong typographic hierarchy.
**Constraint:** Keep 2-panel layout (graph + chat). Keep existing component structure.

### 4C-2: Color & Typography Changes

**Palette shift:**
- Background: `#f8fafc` (was `#f8fbff` gradient)
- Surface (cards): `#ffffff`
- Border: `#e5e7eb` (was `#dbe5f0`)
- Text primary: `#111827` (was `#1a1a1a`)
- Text muted: `#6b7280` (was `#9e9e9e`)
- Accent: `#2563eb` (keep blue, clean)
- Sidebar: `#f9fafb`
- Graph bg: `#fafafa` with subtle dot grid

**Typography:**
- Font: Inter (keep, it's enterprise-standard)
- Scale: 12px sidebar labels (uppercase, 0.08em tracking) / 14px body / 16px headings
- No gradient text, no decorative type

**Node styling:**
- Header bar: solid `#111827` for all container types (no per-type color)
- Cleaner border: `1px solid #e5e7eb`, `border-radius: 8px`
- Shadow: `0 1px 3px rgba(0,0,0,0.06)` — subtle, not layered
- No hover scale transform — use shadow depth change only
- Font: DM Sans or Inter (enterprise neutral)

**Edge labels:**
- Keep backdrop blur
- Reduce border-radius: 8px
- Muted border: `#e5e7eb`
- Background: `rgba(255,255,255,0.95)` — solid, not glassy

### 4C-3: Layout Refinements

**Graph container:**
- Remove gradient overlays and radial atmospheric effects
- Keep dot grid background: `radial-gradient(circle, #e1e4e8 1px, transparent 1px)`
- Border: `1px solid #e5e7eb`, `border-radius: 14px`

**Metrics bar (top of graph panel):**
- Clean horizontal layout
- Level pills: outlined by default, filled when active
- Extract button: solid `#2563eb`, no gradient
- Remove glassmorphism, use solid surfaces

**Chat panel:**
- Keep avatar + title + subtitle pill header
- Message bubbles: clean `#f3f4f6` background, `1px solid #e5e7eb`
- Input: `#f9fafb` background, `1px solid #e5e7eb` border
- Review buttons: outlined style, blue hover fill
- No gradient backgrounds anywhere

**Sidebar (filters):**
- Section headers: 10px, uppercase, `#374151`, 0.08em tracking
- Clean checkbox/radio with `#2563eb` accent
- Collapsible sections: simple chevron, no animation

### 4C-4: Accessibility Fixes

- Tooltip `position: fixed` → `position: absolute` with `position: relative` parent (fix z-index stacking context)
- Focus rings: visible `outline: 2px solid #2563eb` on all interactive elements
- Contrast: all text meets 4.5:1 minimum (muted text `#6b7280` on `#ffffff` = 4.6:1 ✓)
- `cursor: pointer` on all interactive cards and buttons

### 4C-5: Implementation Files

| File | Changes |
|------|---------|
| `CodeArchitectureViewer.scss` | Color tokens, typography, node styling, edge labels, layout spacing |
| `NodeDetailsPanel.tsx` | Chat panel header, message bubble styling, input field styling |
| `MetricsBar.tsx` | Button styles, pill styles, layout tightening |
| `FiltersSidebar.tsx` | Section header typography, checkbox styling |
| `CustomNode.tsx` | Node card: header color, shadow, hover state |
| `C4Edge.tsx` | Edge label: border-radius, backdrop blur reduction |

---

## 5. Stream D — Skill Integration

### 5D-1: Hard-Rule Auto-Invoke

**Mechanism:** Wrapper script approach

**File:** `.claude/skills/superpowers-brainstorm-wrapper.sh`

```bash
#!/bin/bash
# Wraps brainstorming skill to auto-inject ui-ux-pro-max context
# Invokes ui-ux-pro-max search when UI keywords detected in the request

UI_KEYWORDS="ui|ux|component|layout|button|color|typography|palette|font|spacing|accessibility|tooltip|panel|sidebar|graph|visual|design|style|professional|enterprise"

if echo "$*" | grep -iqE "$UI_KEYWORDS"; then
  echo "[superpowers] UI context detected — running ui-ux-pro-max search..."
  # Run design system search and persist result
  python3 .claude/skills/ui-ux-pro-max/scripts/search.py \
    "enterprise dashboard architecture visualization" \
    --design-system \
    --persist \
    -p "KnowledgeForge" \
    -f markdown 2>/dev/null || true
fi

# Then invoke brainstorming as normal
```

**Integration point:** Edit `superpowers:brainstorming` skill to prepend the ui-ux-pro-max invocation at session start when UI context is detected.

**Implementation:** Add a `preamble` check at the top of the brainstorming skill that:
1. Scans incoming prompt for UI keywords
2. If found: runs `ui-ux-pro-max` design system search with `--persist` for "KnowledgeForge"
3. Injects the resulting design system context into the brainstorming session
4. Then proceeds with normal brainstorming workflow

### 5D-2: KnowledgeForge Design System

**Output file:** `design-system/MASTER.md`

Generated by: `python3 skills/ui-ux-pro-max/scripts/search.py "enterprise dashboard architecture visualization" --design-system --persist -p "KnowledgeForge"`

**Override file:** `design-system/pages/knowledgeforge-architecture-viewer.md`

Covers:
- Enterprise Dashboard color palette (derived from ui-ux-pro-max enterprise style)
- Typography: Inter font family, scale
- Component tokens: card border-radius, shadow depth, spacing rhythm
- Anti-patterns specific to this UI (no emojis as icons, no gradient text, no hover scale)

---

## 6. Module Design Blocks

### Module: `tests/harness/omnipay_harness.py`
- **Responsibility:** Provides deterministic extraction runs against OmniPay demo repos with git initialization
- **Interface:** Fixtures: `omnipay_repo(name)`, `extract_containers(path)`, `extract_context(path)`
- **Dependencies:** `StructureDetector`, `ContextManager`, `GitHubDownloader`
- **Size target:** ~150 lines

### Module: `tests/e2e/test_edge_cases.py`
- **Responsibility:** Validates extraction behavior on 5 edge case services (Rust, symlinks, multi-lang, conflicted ownership, no ownership)
- **Interface:** Pytest class per edge case, one assertion method per scenario
- **Dependencies:** `omnipay_harness` fixtures
- **Size target:** ~200 lines

### Module: `app/services/c4/containers/rust_detector.py` (NEW)
- **Responsibility:** Detect Rust services via Cargo.toml and .rs source files
- **Interface:** `detect_rust(repo_path: Path) -> List[dict]`
- **Dependencies:** `Path.glob`, file reading
- **Size target:** ~80 lines

### Module: `CodeArchitectureViewer.scss` (refactored)
- **Responsibility:** Enterprise Dashboard design tokens and component styles
- **Interface:** CSS custom properties for colors, spacing, typography
- **Dependencies:** None
- **Size target:** ~400 lines (tightened from ~2400)

### Module: `.claude/skills/ui-ux-pro-max-auto.sh` (NEW)
- **Responsibility:** Auto-invoke ui-ux-pro-max when brainstorming detects UI context
- **Interface:** Shell script; runs `search.py --persist` then returns
- **Dependencies:** `ui-ux-pro-max` skill installed
- **Size target:** ~30 lines

---

## 7. Scope Boundaries

**In scope:**
- New pytest fixtures and test files in `tests/e2e/`
- Rust detector (new file)
- Symlink handling patch to `structure_detector.py`
- Multi-lang tiering patch to `metadata_detector.py`
- SCSS token refactor + layout tightening
- Skill auto-invoke wrapper script

**Out of scope:**
- Changing the 2-panel layout structure
- Adding new panels or views
- Backend API changes beyond bug fixes
- Database schema changes
- Changing C4 extraction logic (only fixing detected gaps)

---

## 8. Verification

### Backend
```bash
make quick-check                           # API starts, imports OK
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py -v
docker compose exec api python -m pytest tests/e2e/test_omnipay_harness.py -v
docker compose exec api python -m pytest tests/e2e/test_provider_catalog.py -v
docker compose exec api python -m pytest tests/e2e/test_llm_enrichment.py -v
```

### UI
```bash
cd sources/UI && npm run fix-all
cd sources/UI && npm run test
# Manual: open http://localhost:3000, verify Enterprise Dashboard look
```

### Skill
- Brainstorming with any UI keyword triggers ui-ux-pro-max search automatically
- `design-system/MASTER.md` exists and is non-empty
