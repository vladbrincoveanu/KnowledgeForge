# Design: Three-Fix Sprint — Com) Bug, Review Prompts, Graph Layout

**Date:** 2026-04-30
**Status:** Draft
**Type:** Bug Fix + Architectural Cleanup

---

## Context

Three independent bugs surfaced during a UI review of the `/code-architecture` page with the bundled Airbyte demo:

1. **`Com)` entity name** — A URL `https://api.airbyte.com).` extracted from `docs/terraform-documentation.md` produces a context-level entity named `Com)` due to three compounding bugs in URL parsing.
2. **Useless review prompts** — The human-review prompt suggestions for ambiguous dependencies are hardcoded f-string templates with no LLM involvement and no actual evidence passed.
3. **Sparse graph layout** — The container-level graph renders 12 Airbyte containers as a single disconnected vertical column because: (a) the relationship extraction pipeline produces malformed edges (`source: "runtime"`, `dest: None`), and (b) the UI's fallback layout is designed for HTTP-method grouping, not C4 container diagrams.

The graph problem has a deeper root cause: the UI runs **two parallel node/edge pipelines** that were never designed to interoperate. Pipeline A (the primary entity/relationship system) and Pipeline B (`generateC4Edges`, a legacy OmniPay-specific approach) create separate node sets with incompatible ID schemes, resulting in zero resolved edges in the merged graph.

**Decision:** Adopt Option A — kill Pipeline B, fix Pipeline A. This commit is to the entity/relationship model which is the correct architectural path for C4 diagrams.

---

## Fix 1: `Com)` Garbled Entity Name

### Root Cause

Three compounding bugs in `app/services/c4/context/dependency_detector.py`:

| Line | Bug |
|------|-----|
| 89 | `GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"']+"` — `)` is not in the exclusion class, so Markdown like `[Airbyte](https://api.airbyte.com).` captures the trailing `).` as part of the URL |
| 1109 | `urlparse()` preserves `)` in the hostname (valid URI character) |
| 1115 | `host.split(".")` on `"api.airbyte.com)."` → `['api', 'airbyte', 'com)', '']` — the trailing empty string shifts `parts[-2]` from the intended segment (`airbyte`) to `com)` |

### Module: URL Name Extraction Fix

- **File:** `sources/Api/app/services/c4/context/dependency_detector.py`
- **Responsibility:** Extract a clean display name from a raw URL string
- **Interface:** Input: URL string. Output: cleaned display name string
- **Dependencies:** `urlparse` from stdlib
- **Size target:** +2 lines within existing ~15-line method

### Changes

**Change 1 — Line 89:** Add `)` to the URL regex exclusion set:

```python
# Before
GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"']+"
# After
GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"')]+"
```

**Change 2 — Line 1115 (within `_extract_service_name_from_url`):** Strip trailing dots and parens from hostname before splitting:

```python
# After urlparse(), before split:
host = host.rstrip('.)')
parts = host.split(".")
```

**Verification:** For input `https://api.airbyte.com).`:
- `urlparse` gives hostname `api.airbyte.com).`
- After `rstrip('.)')`: `api.airbyte.com)`
- `split('.')`: `['api', 'airbyte', 'com)']`
- `parts[-2]`: `'airbyte'` → `'Airbyte'` (correct)

For `https://stripe.com).` → `'Stripe'` (correct).
For `https://docs.aws.amazon.com` → `'Amazon'` (correct, `parts[-2] = 'amazon'`).

### Tests

Add parametrized unit test in `test_dependency_detector.py`:

```python
@pytest.mark.parametrize("url,expected", [
    ("https://api.airbyte.com).", "Airbyte"),
    ("https://stripe.com).", "Stripe"),
    ("https://docs.aws.amazon.com", "Amazon"),
    ("https://api.openai.com).", "Openai"),
])
def test_extract_service_name_from_url_strips_trailing_junk(url, expected):
    detector = DependencyDetector(...)
    result = detector._extract_service_name_from_url(url)
    assert result == expected
```

---

## Fix 2: Smarter Review Prompts

### Root Cause

`_build_review_prompts()` at line 799 is two hardcoded f-string templates. No LLM is called. The dependency dict is not passed in, so templates interpolate garbage (`Com)`) and generic text ("payment-platform workflow"). The prompts tell the user to "ask about responsibilities, ownership, or relationships" instead of using the actual extracted evidence.

### Module: Review Prompt LLM Integration

- **File:** `sources/Api/app/services/c4/context/dependency_detector.py`
- **Responsibility:** Generate 2-3 context-specific prompt starters for ambiguous dependency classification
- **Interface:** Input: `context_name`, `dep_type`, `dep` dict. Output: `list[str]`
- **Dependencies:** `LLMManager` (existing), dep evidence from caller
- **Size target:** ~40 lines

### Changes

**Change 1 — Line 743:** Pass full `dep` dict to `_build_review_prompts`:

```python
# Before
enriched["suggested_prompts"] = self._build_review_prompts(context_name, final_type)
# After
enriched["suggested_prompts"] = self._build_review_prompts(context_name, final_type, dep)
```

**Change 2 — Lines 799-810:** Refactor `_build_review_prompts` to call LLM:

```python
def _build_review_prompts(self, context_name: str, dep_type: str, dep: dict) -> list[str]:
    """Generate context-specific prompt starters for ambiguous dependencies."""
    evidence = dep.get("context") or dep.get("url") or dep.get("name") or "unknown source"
    confidence = dep.get("classification_confidence", 0.5)
    prompt = (
        f"A C4 architecture dependency was detected:\n"
        f"- Name: {context_name}\n"
        f"- Type: {dep_type}\n"
        f"- Evidence: {evidence}\n"
        f"- Classification confidence: {confidence:.0%} (below 70% threshold)\n\n"
        f"Generate exactly 2 short prompt starters (≤25 words each) to help a human decide:\n"
        f"1. Whether this belongs at Context level (external business actor/SaaS) or Container level (technical infra)\n"
        f"2. What specific architectural role this dependency likely plays\n"
        f"Return ONLY a JSON array of strings, no markdown: [\"prompt1\", \"prompt2\"]"
    )
    try:
        llm = get_llm_manager()
        if llm:
            response = llm.generate_text(prompt, max_tokens=200, temperature=0.3)
            parsed = json.loads(response.strip())
            if isinstance(parsed, list) and len(parsed) >= 2:
                return parsed[:2]
    except Exception:
        pass
    # Fallback: static prompt using actual evidence
    return [
        f"Based on being used for {dep_type}: is {context_name} a business actor or technical detail?",
        f"What architecture role does {context_name} play given it was found in: {evidence[:80]}?",
    ]
```

**Note:** The static fallback now references the actual `dep_type` and `evidence` instead of hardcoded "payment-platform".

### Tests

```python
def test_build_review_prompts_uses_actual_evidence(mocker):
    detector = DependencyDetector(...)
    dep = {
        "name": "api.airbyte.com",
        "context": "docs/terraform-documentation.md",
        "type": "external_service",
        "classification_confidence": 0.6,
    }
    # With mock LLM unavailable → fallback
    mocker.patch.object(detector, "_get_llm", return_value=None)
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert "payment-platform" not in prompts[0]  # No generic template
    assert "docs/terraform-documentation.md" in prompts[1]  # Uses actual evidence

def test_build_review_prompts_llm_success(mocker):
    detector = DependencyDetector(...)
    mock_llm = mocker.MagicMock()
    mock_llm.generate_text.return_value = '["Is api.airbyte.com a SaaS API or internal infra?", "What services does it provide to the codebase?"]'
    mocker.patch.object(detector, "_get_llm", return_value=mock_llm)
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert len(prompts) == 2
```

---

## Fix 3: Graph Layout & Pipeline Cleanup

### Root Cause (Twofold)

**Data problem:** The bundled `c4_architecture.json` has no `container_level` key. All 3 edges in `relationships.containers` are malformed: `source: "runtime"`, `destination: None`. Investigation needed — "runtime" is not a container name in Airbyte's dataset, and `destination: None` indicates the YAML/JSON relationship parser is failing to extract the `to` field.

**Rendering problem:** The UI has two parallel pipelines:
- **Pipeline A:** Builds nodes from `container_level.entities`, edges from `container_level.relationships` via `buildRenderedEdges()`
- **Pipeline B:** Builds container frame nodes + ghost nodes + dependency edges via `generateC4Edges()`, which uses its own ID scheme (`container_${name}`)

Pipeline B was designed for OmniPay's `omnipay-` prefixed container names and hardcoded prefix stripping. It produces a separate node set with IDs incompatible with Pipeline A. When merged, `generateC4Edges` resolves zero edges because its container IDs don't match Pipeline A's entity IDs.

**Decision:** Kill Pipeline B entirely. Fix Pipeline A to correctly populate `container_level` from the extraction pipeline, and fix the UI to render containers properly from Pipeline A's entity data.

---

### Sub-module 3A: Fix Relationship Extraction (Backend)

**Module:** Relationship builder in `dependency_detector.py` or `context_manager.py`
**Status:** Needs investigation — the exact file and line producing `source: "runtime"` is not yet confirmed.

**Known data points:**
- The 3 malformed edges are: `openapi2jsonschema uses docker`, `base-normalization uses docker`, `docusaurus uses generator`
- The `source: "runtime"` suggests a variable named `runtime` is being used as a container name somewhere in the relationship builder
- `destination: None` suggests the YAML key `to` or `destination` is not being parsed

**Investigation steps:**
1. Find where `relationships.containers` is built in the extraction pipeline
2. Trace how `source: "runtime"` could be produced for `openapi2jsonschema uses docker`
3. Fix the field extraction so `from` and `to` map to actual container names

**Success criteria:** After fix, `relationships.containers[].source` and `relationships.containers[].destination` must both be non-None strings matching names in `containers[]`.

### Module: Relationship Extraction Fix (investigation required)

- **File:** Investigation required — likely `context_manager.py` or `dependency_detector.py`
- **Responsibility:** Build valid container-level relationships with matching source/destination names
- **Interface:** Reads source files (YAML/JSON), emits `relationships.containers[]`
- **Dependencies:** Container entity builder
- **Size target:** ~20 lines once root cause found

### Sub-module 3B: Kill Pipeline B (Frontend)

**Module:** `generateC4Edges` removal
- **File:** `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
- **Responsibility:** Remove the legacy OmniPay-specific container/edge pipeline
- **Interface:** N/A (removal)
- **Dependencies:** Pipeline A must be working first (3A)
- **Size target:** -160 lines

**Changes:**

1. **Delete `generateC4Edges()` function** (lines 105-239):
   - Removes container ID mapping with `omnipay-` prefix stripping (lines 116-118, 143-145)
   - Removes ghost node creation for unresolved externals
   - Removes legacy edge creation from `dependencies_internal`/`dependencies_external`

2. **Remove Pipeline B call site** (lines 2140-2149):
   ```typescript
   // DELETE:
   const { nodes: ghostNodes, edges: dependencyEdges } =
     selectedLevel === "container_level" &&
     (architecture?.containers?.length > 0 ||
       (architecture?.relationships?.containers?.length ?? 0) > 0)
       ? generateC4Edges(...)
       : { nodes: [], edges: [] };
   ```
   Replace with: `const ghostNodes = []; const dependencyEdges = [];`

3. **Remove `contextExternalEntities` building** (lines 2132-2138) — no longer needed since ghost nodes are gone.

4. **Remove `ghostNodeIds` and `ghostNodes` from merged nodes** (line 2152):
   ```typescript
   // Before: const mergedNodes = [...rfNodes, ...ghostNodes];
   // After:
   const mergedNodes = rfNodes;
   ```

5. **Remove `contextExternalIdByName` and related normalization** (lines 122-131) — used only by Pipeline B.

6. **Remove `omnipay-` prefix stripping** from `resolveId` (lines 143-145) — Pipeline A uses entity IDs from the backend, not name mangling.

### Sub-module 3C: Smarter Container Layout (Frontend)

**Module:** `getLayoutedElements` refactor
- **File:** `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
- **Responsibility:** Position container/component nodes intelligently regardless of edge count
- **Interface:** Input: `(nodes: Node[], edges: Edge[])`. Output: `{ nodes: Node[], edges: Edge[] }`
- **Dependencies:** `dagre` library, ReactFlow node types
- **Size target:** ~80 lines changed, net reduction of ~35 lines due to pipeline B removal

#### Change 1: Connected graph layout (dagre — reduced spacing)

```typescript
// Current dagre config (lines 422-431):
dagreGraph.setGraph({
  rankdir: direction,
  align: "UL",
  ranksep: 240,   // → 160
  nodesep: 155,    // → 100
  edgesep: 70,     // → 50
  marginx: 150,    // → 80
  marginy: 150,    // → 80
  ranker: "network-simplex",
});
```

#### Change 2: Disconnected graph layout (grid — centered, multi-column)

Replace the HTTP-method grouped grid (lines 370-412) with a centered grid:

```typescript
if (!hasRelationships && nodes.length > 0) {
  const nodeW = 240;
  const nodeH = 130;
  const gapX = 60;
  const gapY = 60;
  const cols = Math.min(6, Math.ceil(Math.sqrt(nodes.length)));
  const rows = Math.ceil(nodes.length / cols);
  const canvasW = 1400; // approximate viewport width
  const startX = Math.max(40, (canvasW - cols * (nodeW + gapX)) / 2);
  const startY = 60;

  nodes.forEach((node, idx) => {
    const row = Math.floor(idx / cols);
    const col = idx % cols;
    return {
      ...node,
      position: {
        x: startX + col * (nodeW + gapX),
        y: startY + row * (nodeH + gapY),
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });
  return { nodes: layoutedNodes, edges };
}
```

#### Change 3: Container frame sizing (no minimum)

```typescript
// Current (lines 318-322):
container.style = {
  width: Math.max(800, contentWidth),   // → remove 800 minimum
  height: Math.max(520, contentHeight),  // → remove 520 minimum
};

// After: size to content only
container.style = {
  width: Math.max(400, contentWidth),
  height: Math.max(280, contentHeight),
};
```

#### Change 4: Container spacing reduction

Line 274: `const containerSpacing = 180;` → `const containerSpacing = 80;`

#### Change 5: FitView tighter padding

In `fitView` call (line 2198):
```typescript
fitView({
  padding: 0.10,    // was 0.20
  maxZoom: 2.0,     // was 1.5
  // ...
});
```

---

## Testing Strategy

| Fix | Test Type | Test Location |
|-----|-----------|--------------|
| 1 — `Com)` URL fix | Unit (parametrized, 3 cases) | `test_dependency_detector.py` |
| 2 — Review prompts | Unit (mock LLM + fallback) | `test_dependency_detector.py` |
| 3A — Relationship extraction | Integration (regenerate JSON, verify edges) | `test_airbyte_extraction.py` |
| 3B — Kill Pipeline B | Existing Playwright E2E (01, 02, 03, 04, 05) must pass | `sources/UI/e2e/specs/` |
| 3C — Smarter layout | Visual inspection + Playwright screenshot | `02-architecture-graph.spec.ts` |

---

## Migration Plan

### Phase 1: Backend fixes (no UI impact)
1. Fix 1 — `Com)` URL parsing
2. Fix 2 — LLM review prompts
3. Run unit tests
4. Commit: `fix(api): Com) entity name + smarter review prompts`

### Phase 2: Relationship data fix
5. Fix 3A — Investigate and fix relationship extraction pipeline
6. Regenerate `c4_architecture.json` via `make generate-demo`
7. Verify `relationships.containers[].source` and `.destination` are valid container names
8. Commit: `fix(api): correct container relationship source/destination fields`

### Phase 3: UI Pipeline B removal
9. Fix 3B — Remove `generateC4Edges` and all Pipeline B code
10. Verify Playwright E2E passes: `npm run test:e2e`
11. Commit: `refactor(ui): remove legacy OmniPay pipeline B from graph rendering`

### Phase 4: Layout improvements
12. Fix 3C — Apply dagre spacing, centered grid, tighter containers
13. Visual verification at `http://localhost:3000/code-architecture` (container level)
14. Commit: `feat(ui): denser container-level graph layout`

---

## Open Questions

1. **3A root cause:** The exact file and line producing `source: "runtime"` is not yet confirmed. The investigation step may reveal a different fix than described above.
2. **OmniPay compatibility:** Removing Pipeline B's `omnipay-` prefix stripping may break OmniPay demo. Verify that OmniPay containers are named consistently in the entity ID scheme after the extraction pipeline fix.
3. **LLM availability:** Fix 2 requires `LLMManager` to be available. A graceful fallback (static prompts using actual evidence) is included, but the LLM path should be tested when LM Studio is running.
