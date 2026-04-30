# Three-Fix Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `Com)` garbled entity name, upgrade review prompts to use LLM with actual evidence, and replace the sparse disconnected graph layout with denser packing — including killing the legacy OmniPay-specific Pipeline B.

**Architecture:** Three independent fixes. Fixes 1 and 2 are backend-only, touching `dependency_detector.py`. Fix 3 is split: 3A (backend relationship extraction investigation), 3B (UI Pipeline B removal), 3C (UI layout refactor). Fix 3B and 3C require Fix 3A to produce valid edges first.

**Tech Stack:** Python (FastAPI backend), TypeScript/ReactFlow (UI), dagre, Playwright E2E

---

## Files Overview

| File | Responsibility |
|------|---------------|
| `sources/Api/app/services/c4/context/dependency_detector.py` | URL parsing (Fix 1), review prompts (Fix 2), relationship building (Fix 3A investigation) |
| `sources/Api/tests/unit/services/c4/test_dependency_detector.py` | Unit tests for Fix 1 and Fix 2 |
| `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx` | Pipeline B removal (3B), layout refactor (3C) |
| `sources/UI/e2e/specs/06-omnipay-smoke.spec.ts` | Smoke test may need update after 3B |

---

## Fix 1: `Com)` Garbled Entity Name

**Files:**
- Modify: `sources/Api/app/services/c4/context/dependency_detector.py:89`, `dependency_detector.py:1115`
- Test: `sources/Api/tests/unit/services/c4/test_dependency_detector.py`

### Task 1: Write failing unit tests for URL name extraction

- [ ] **Step 1: Write the failing tests**

Open `sources/Api/tests/unit/services/c4/test_dependency_detector.py` and add a parametrized test at the end of the file:

```python
@pytest.mark.parametrize("url,expected", [
    ("https://api.airbyte.com).", "Airbyte"),
    ("https://stripe.com).", "Stripe"),
    ("https://docs.aws.amazon.com", "Amazon"),
    ("https://api.openai.com).", "Openai"),
    # Also verify normal URLs still work
    ("https://github.com/user/repo", "Github"),
    ("https://api.stripe.com/v1/charges", "Stripe"),
])
def test_extract_service_name_from_url_strips_trailing_junk(temp_repo, url, expected):
    """URLs extracted from markdown often have trailing punctuation; name must be clean."""
    from app.services.c4.context.dependency_detector import DependencyDetector
    detector = DependencyDetector(repo_path=temp_repo)
    result = detector._extract_service_name_from_url(url)
    assert result == expected, f"URL {url!r} → {result!r}, expected {expected!r}"
```

- [ ] **Step 2: Run tests to verify they fail for the junk URLs**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py::test_extract_service_name_from_url_strips_trailing_junk -v`

Expected: FAIL for `("https://api.airbyte.com).", "Airbyte")` → got `"Com)"`; may pass for clean URLs.

- [ ] **Step 3: Fix the regex at line 89**

Find line 89 in `dependency_detector.py`:
```python
GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"']+"
```
Change to:
```python
GENERIC_URL_PATTERN = r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"')\];,}<>]+"
```

- [ ] **Step 4: Fix the hostname cleanup at line 1115**

Find the `_extract_service_name_from_url` method around line 1106. Change:

```python
    def _extract_service_name_from_url(self, url: str) -> str:
        """Extract a display name from a URL."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return "External Service"
        host = parsed.hostname or parsed.netloc or parsed.path
        if not host:
            return "External Service"
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").replace("_", " ").title()
        return host.replace("-", " ").replace("_", " ").title()
```

Add `host = host.rstrip('.)')` before the split:

```python
        host = parsed.hostname or parsed.netloc or parsed.path
        if not host:
            return "External Service"
        host = host.rstrip('.)')          # NEW: strip trailing punctuation that breaks split indexing
        parts = host.split(".")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py::test_extract_service_name_from_url_strips_trailing_junk -v`

Expected: PASS for all 6 parametrized cases.

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git add sources/Api/app/services/c4/context/dependency_detector.py sources/Api/tests/unit/services/c4/test_dependency_detector.py
git commit -m "fix(api): strip trailing punctuation from URLs before extracting service names"
```

---

## Fix 2: Smarter Review Prompts (LLM Integration)

**Files:**
- Modify: `sources/Api/app/services/c4/context/dependency_detector.py:107-111`, `dependency_detector.py:743`, `dependency_detector.py:799-810`
- Test: `sources/Api/tests/unit/services/c4/test_dependency_detector.py`

### Task 2: Store `llm_manager` on `DependencyDetector`

- [ ] **Step 1: Verify current `__init__` signature**

Find `DependencyDetector.__init__` around line 107:

```python
def __init__(self, repo_path: Path, llm_manager=None, enable_classification: bool = True):
    self.repo_path = Path(repo_path).resolve()
    self.classifier = DependencyClassifier(llm_manager) if enable_classification else None
    self.last_review_items: list[dict[str, Any]] = []
```

- [ ] **Step 2: Add `self.llm_manager = llm_manager`**

Insert `self.llm_manager = llm_manager` after line 110 (after the classifier line):

```python
def __init__(self, repo_path: Path, llm_manager=None, enable_classification: bool = True):
    self.repo_path = Path(repo_path).resolve()
    self.llm_manager = llm_manager          # NEW: store for _build_review_prompts
    self.classifier = DependencyClassifier(llm_manager) if enable_classification else None
    self.last_review_items: list[dict[str, Any]] = []
```

- [ ] **Step 3: Verify no regressions**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py -v -x`

Expected: All existing tests still pass.

- [ ] **Step 4: Commit**

Run:
```bash
git add sources/Api/app/services/c4/context/dependency_detector.py
git commit -m "refactor(api): store llm_manager on DependencyDetector for review prompt generation"
```

### Task 3: Refactor `_build_review_prompts` to use LLM

- [ ] **Step 1: Write failing unit tests**

Add to `test_dependency_detector.py`:

```python
def test_build_review_prompts_uses_actual_evidence(temp_repo):
    """When LLM unavailable, fallback prompts must reference actual dep evidence."""
    from app.services.c4.context.dependency_detector import DependencyDetector
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=None)
    dep = {
        "name": "api.airbyte.com",
        "context": "docs/terraform-documentation.md",
        "type": "external_service",
        "classification_confidence": 0.6,
        "review_threshold": 0.7,
    }
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert len(prompts) == 2
    assert "payment-platform" not in prompts[0]      # No generic template
    assert "terraform" in prompts[1]                  # Uses actual evidence source
    assert "0.7" in prompts[0] or "70%" in prompts[0]  # Uses actual threshold


def test_build_review_prompts_llm_success(temp_repo, mocker):
    """LLM returns valid JSON array → prompts returned directly."""
    mock_llm = mocker.MagicMock()
    mock_llm.generate_text.return_value = (
        '["Is api.airbyte.com a SaaS API or internal infra?", "What services does it provide?"]'
    )
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "...", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert len(prompts) == 2


def test_build_review_prompts_handles_markdown_fence(temp_repo, mocker):
    """LLM sometimes wraps JSON in ```json fences — must extract correctly."""
    mock_llm = mocker.MagicMock()
    mock_llm.generate_text.return_value = '```json\n["Prompt one?", "Prompt two?"]\n```'
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "...", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("x", "service", dep)
    assert len(prompts) == 2
    assert prompts[0] == "Prompt one?"


def test_build_review_prompts_corrupt_json_falls_back(temp_repo, mocker):
    """LLM returns malformed text → fallback prompts used."""
    mock_llm = mocker.MagicMock()
    mock_llm.generate_text.return_value = "Here are your prompts, I'm not sure..."
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "src/main.rs", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("x", "service", dep)
    assert len(prompts) == 2
    assert "payment-platform" not in prompts[0]  # Still no generic template
```

- [ ] **Step 2: Run tests — expect 3 failures (llm_success, markdown_fence, corrupt_json fallbacks)**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_uses_actual_evidence tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_llm_success tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_handles_markdown_fence tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_corrupt_json_falls_back -v`

Expected: 3 failures for tests using `mocker` (unimplemented method signature), 1 pass for `uses_actual_evidence`.

- [ ] **Step 3: Change `_build_review_prompts` call at line 743 to pass `dep`**

Find line 743 (approximately) in `_enrich_dependency`. It should read:

```python
enriched["suggested_prompts"] = self._build_review_prompts(context_name, final_type)
```

Change to:

```python
enriched["suggested_prompts"] = self._build_review_prompts(context_name, final_type, dep)
```

- [ ] **Step 4: Replace `_build_review_prompts` method (lines 799-810)**

Find the `_build_review_prompts` method. Replace the entire method with:

```python
    def _build_review_prompts(
        self, context_name: str, dep_type: str, dep: dict[str, Any]
    ) -> list[str]:
        """Generate context-specific prompt starters for ambiguous dependencies.

        Uses LLM if available to generate tailored prompts based on actual
        dependency evidence (source file, URL, classification confidence).
        Falls back to static prompts using actual dep evidence if LLM unavailable.
        """
        evidence = dep.get("context") or dep.get("url") or dep.get("name") or "unknown source"
        confidence = dep.get("classification_confidence", 0.5)
        review_threshold = dep.get("review_threshold", 0.7)
        prompt = (
            f"A C4 architecture dependency was detected:\n"
            f"- Name: {context_name}\n"
            f"- Type: {dep_type}\n"
            f"- Evidence: {evidence}\n"
            f"- Classification confidence: {confidence:.0%} "
            f"(below {review_threshold:.0%} threshold)\n\n"
            f"Generate exactly 2 short prompt starters (25 words or fewer each) "
            f"to help a human decide:\n"
            f"1. Whether this belongs at Context level (external business actor/SaaS) "
            f"or Container level (technical infra)\n"
            f"2. What specific architectural role this dependency likely plays\n"
            f'Return ONLY a JSON array of strings, no markdown: ["prompt1", "prompt2"]'
        )
        try:
            if self.llm_manager:
                response = self.llm_manager.generate_text(
                    prompt, max_tokens=200, temperature=0.3
                )
                text = response.strip()
                # Strip markdown code fences
                text = text.removeprefix("```json").strip().removeprefix("```").strip()
                # Find first JSON array [...] in response
                match = re.search(r'\[[\s\S]*\]', text)
                if match:
                    parsed = json.loads(match.group())
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        return parsed[:2]
        except Exception:
            pass
        # Fallback: static prompts using actual evidence
        return [
            f"Based on being used for {dep_type}: is {context_name} a business actor "
            f"or technical detail?",
            f"What architecture role does {context_name} play given it was found in: "
            f"{evidence[:80]}?",
        ]
```

- [ ] **Step 5: Run tests — expect all 4 to pass**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_uses_actual_evidence tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_llm_success tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_handles_markdown_fence tests/unit/services/c4/test_dependency_detector.py::test_build_review_prompts_corrupt_json_falls_back -v`

Expected: PASS.

- [ ] **Step 6: Run full dependency detector test suite**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py -v`

Expected: All tests pass (existing + new).

- [ ] **Step 7: Commit**

Run:
```bash
git add sources/Api/app/services/c4/context/dependency_detector.py sources/Api/tests/unit/services/c4/test_dependency_detector.py
git commit -m "feat(api): LLM-powered review prompts with actual dependency evidence"
```

---

## Fix 3A: Investigate and Fix Relationship Extraction

> **Status:** Investigative — the exact file and line producing `source: "runtime"` is not yet confirmed. The steps below use a structured trace approach. If the root cause is found in a different file than expected, adjust accordingly.

**Files:**
- Investigate: `sources/Api/app/services/c4/context/dependency_detector.py`, `sources/Api/app/services/c4/context/context_manager.py`
- Regenerate: `sources/Api/c4_architecture.json` via Docker exec

### Task 4: Trace the malformed relationship source

- [ ] **Step 1: Find where `relationships.containers` is built in the pipeline**

Search for `relationships.containers` or `"containers"` as a relationship key in the API codebase:

Run: `grep -rn "relationships.*containers\|relationships\['containers'\]\|relationships\.containers" /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/ --include="*.py" | head -20`

Note: The result file `c4_architecture.json` is built by the extraction pipeline. The key `relationships.containers` must be populated somewhere in `context_manager.py`, `dependency_detector.py`, or the C4 serialization code.

- [ ] **Step 2: Search for the string "runtime" in the context module**

Run: `grep -rn '"runtime"\|"runtime"\|runtime' /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/services/c4/context/ --include="*.py"`

Look for any occurrence of the literal string `"runtime"` or a variable named `runtime` that could end up as a container name in a relationship.

- [ ] **Step 3: Search for where container relationship `from`/`to` fields are set**

Run: `grep -rn 'from.*relationship\|to.*relationship\|relationship.*from\|relationship.*to\|"from"\|"to"' /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/services/c4/context/ --include="*.py" | grep -v test | head -30`

Also search for YAML parsing of `values.yaml` or similar deployment files that might contain `from: runtime`:

Run: `grep -rn "from.*:" /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/services/c4/context/ --include="*.py" | grep -v test | head -30`

- [ ] **Step 4: If "runtime" is found — trace its origin**

If `"runtime"` appears in the search, read the surrounding 20-line context. Determine whether it's:
- A hardcoded string that should be a container name
- A variable name that got stringified incorrectly
- A YAML key that was mistaken for a value

Fix the appropriate line.

- [ ] **Step 5: If "runtime" is NOT found — check relationship field extraction**

If `"runtime"` is not in the source code, the problem is likely in how YAML/JSON relationship entries are parsed. Search for where YAML or JSON files are parsed to produce `relationships.containers`:

Run: `grep -rn "yaml\|toml\|json" /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/services/c4/context/dependency_detector.py | grep -i "load\|parse\|read"`

Check if `_parse_helm_values` or similar methods extract relationships from YAML with `from`/`to` keys. Trace the exact line where `destination: None` could be produced.

- [ ] **Step 6: Fix the relationship extraction**

Once root cause identified, apply the fix. Common patterns to look for:
- `dep.get("to")` returning `None` when key is missing → use `.get("to") or dep.get("destination")`
- `"runtime"` as a hardcoded fallback for unknown container names → replace with correct container name derived from context

The goal: after fix, every entry in `relationships.containers[]` has both `source` and `destination` as non-None strings matching names in `containers[]`.

- [ ] **Step 7: Regenerate `c4_architecture.json`**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge && DEMO_REPO_PATH=/app/sources/demo/airbyte LLM_PROVIDER=none make generate-demo`

Wait for completion (~60 seconds).

- [ ] **Step 8: Verify fixed relationships**

Run:
```bash
curl -s http://localhost:8000/api/v1/code/architecture | python3 -c "
import json, sys
d = json.load(sys.stdin)
rels = d.get('relationships', {}).get('containers', [])
print(f'Container relationships: {len(rels)}')
bad = [r for r in rels if not r.get('source') or r.get('destination') is None or r.get('destination') == 'None']
print(f'Bad relationships: {len(bad)}')
for r in rels:
    print(f'  {r.get(\"source\")} -> {r.get(\"destination\")} | {r.get(\"relationship_type\")}')
"
```

Expected: All 3 (or more) relationships have valid non-None source and destination matching container names. Zero bad relationships.

- [ ] **Step 9: Commit**

Run:
```bash
git add sources/Api/app/services/c4/context/dependency_detector.py  # or whichever file was fixed
git add sources/Api/c4_architecture.json
git commit -m "fix(api): correct container relationship source/destination fields"
```

---

## Fix 3B: Kill Pipeline B in UI

> **Prerequisite:** Fix 3A must produce valid edges first. Do not skip Fix 3A.

**Files:**
- Modify: `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
- Test: `sources/UI/e2e/specs/01-extraction.setup.ts`, `02-architecture-graph.spec.ts`, `06-omnipay-smoke.spec.ts`

### Task 5: Remove `generateC4Edges` function and its call site

- [ ] **Step 1: Read the `generateC4Edges` function boundaries**

Find `generateC4Edges` function start (look for `const generateC4Edges` or `function generateC4Edges`):

Run: `grep -n "generateC4Edges\|function generateC4Edges\|const generateC4Edges" /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

Note the line numbers. The function spans approximately lines 105-239.

- [ ] **Step 2: Delete the entire `generateC4Edges` function**

Delete all lines from the function declaration through its closing brace/return statement.

- [ ] **Step 3: Remove the Pipeline B call site (around lines 2140-2149)**

Find and delete this block:
```typescript
const { nodes: ghostNodes, edges: dependencyEdges } =
  selectedLevel === "container_level" &&
  (architecture?.containers?.length > 0 ||
    (architecture?.relationships?.containers?.length ?? 0) > 0)
    ? generateC4Edges(...)
    : { nodes: [], edges: [] };
```

Replace with:
```typescript
const ghostNodes: Node[] = [];
const dependencyEdges: Edge[] = [];
```

- [ ] **Step 4: Update mergedNodes (line ~2152)**

Find `const mergedNodes = [...rfNodes, ...ghostNodes];` and change to:
```typescript
const mergedNodes = rfNodes;
```

- [ ] **Step 5: Remove `contextExternalEntities` building (lines ~2132-2138)**

Delete:
```typescript
const contextExternalEntities = (
  architecture.system_context?.external_dependencies || []
).map((dep: any, idx: number) => ({
  id: `context_external_${idx}`,
  name: dep.context_name || dep.name,
  entity_type: "external_system",
}));
```

- [ ] **Step 6: Remove `contextExternalIdByName` and related normalization (lines ~122-131)**

Delete the `contextExternalIdByName` Map building and all references to it in `resolveId`.

- [ ] **Step 7: Remove `omnipay-` prefix stripping from `resolveId` (lines ~143-145)**

Delete:
```typescript
const stripped = name.startsWith("omnipay-") ? name.slice(8) : name;
if (nameToId.has(stripped))
  return { id: nameToId.get(stripped)!, isGhost: false };
```

Also delete the corresponding entry in `nameToId` building (lines ~116-118).

- [ ] **Step 8: TypeScript compile check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run check-all 2>&1 | head -40`

Expected: No new TypeScript errors (only pre-existing import errors in `containers/` module are acceptable).

Fix any new TypeScript errors caused by removing the function and its types before proceeding.

- [ ] **Step 9: Run Playwright E2E**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run test:e2e 2>&1 | tail -30`

Expected: All tests pass. If `06-omnipay-smoke.spec.ts` fails, see Task 6.

- [ ] **Step 10: Commit**

Run:
```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx
git commit -m "refactor(ui): remove legacy generateC4Edges OmniPay pipeline from graph rendering"
```

### Task 6: Fix OmniPay smoke test after Pipeline B removal

> Only needed if `06-omnipay-smoke.spec.ts` fails after Task 5.

- [ ] **Step 1: Run the OmniPay smoke test in isolation**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run test:e2e -- --grep "OmniPay" 2>&1 | tail -40`

Check the error. If it says a container name is not found, the entity ID format from Pipeline A differs from what the test expects.

- [ ] **Step 2: Inspect Pipeline A's entity IDs for OmniPay**

After extracting OmniPay, the API response at `containers[]` shows the container names. The entity IDs used in Pipeline A's `container_level.entities` will be `container_${name}` (from the fallback entity creation) or the actual entity IDs if `container_level` is populated.

Check what `02-architecture-graph.spec.ts` and `06-omnipay-smoke.spec.ts` are looking for vs what's in the API response. Update test selectors to use dynamic container names from the API response (as `02-architecture-graph.spec.ts` already does for Airbyte).

- [ ] **Step 3: Re-run smoke test**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run test:e2e -- --grep "OmniPay" 2>&1 | tail -20`

Expected: PASS.

- [ ] **Step 4: Commit**

Run:
```bash
git add sources/UI/e2e/specs/06-omnipay-smoke.spec.ts  # or whichever file was updated
git commit -m "test(ui): update OmniPay smoke test for Pipeline A entity IDs"
```

---

## Fix 3C: Smarter Container Layout

> **Prerequisite:** Fix 3A complete (valid edges exist in JSON).

**Files:**
- Modify: `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

### Task 7: Denser disconnected grid layout

- [ ] **Step 1: Find the disconnected grid layout section**

Search for `methodOrder` in `CodeArchitectureViewer.tsx` — this is the HTTP-method grouped grid that fires when `!hasRelationships`. It should be around lines 370-412.

- [ ] **Step 2: Replace the grid with centered multi-column layout**

Replace the entire `if (!hasRelationships && nodes.length > 0)` block with:

```typescript
  if (!hasRelationships && nodes.length > 0) {
    const nodeW = 240;
    const nodeH = 130;
    const gapX = 60;
    const gapY = 60;
    const cols = Math.min(6, Math.ceil(Math.sqrt(nodes.length)));
    const rows = Math.ceil(nodes.length / cols);
    const viewportW = typeof window !== 'undefined' ? window.innerWidth : 1400;
    const startX = Math.max(40, (viewportW - cols * (nodeW + gapX)) / 2);
    const startY = 60;

    const layoutedNodes = nodes.map((node, idx) => {
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

Delete the `methodGroups` Map and `methodOrder` array — they are no longer needed.

### Task 8: Tighter dagre spacing for connected graphs

- [ ] **Step 1: Find dagre config block**

Search for `ranksep: 240` in `CodeArchitectureViewer.tsx` — should be around lines 422-431 inside the `if (edges.length > 0)` dagre branch.

- [ ] **Step 2: Reduce dagre spacing**

Replace:
```typescript
  dagreGraph.setGraph({
    rankdir: direction,
    align: "UL",
    ranksep: 240,
    nodesep: 155,
    edgesep: 70,
    marginx: 150,
    marginy: 150,
    ranker: "network-simplex",
  });
```
With:
```typescript
  dagreGraph.setGraph({
    rankdir: direction,
    align: "UL",
    ranksep: 160,
    nodesep: 100,
    edgesep: 50,
    marginx: 80,
    marginy: 80,
    ranker: "network-simplex",
  });
```

### Task 9: Smaller container frames and tighter spacing

- [ ] **Step 1: Find `containerSpacing = 180` (around line 274)**

Change to:
```typescript
const containerSpacing = 80;
```

- [ ] **Step 2: Find container style min-width/height (around lines 318-322)**

Change:
```typescript
container.style = {
  width: Math.max(800, contentWidth),
  height: Math.max(520, contentHeight),
};
```
To:
```typescript
container.style = {
  width: Math.max(400, contentWidth),
  height: Math.max(280, contentHeight),
};
```

### Task 10: Tighter fitView

- [ ] **Step 1: Find `fitView` call (around line 2198)**

Change `padding: 0.20` to `padding: 0.10` and `maxZoom: 1.5` to `maxZoom: 2.0`.

### Task 11: Verify and commit

- [ ] **Step 1: TypeScript compile check**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run check-all 2>&1 | head -40`

Expected: No new TypeScript errors.

- [ ] **Step 2: Visual inspection**

Start the UI (if not running): `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run dev`

Open `http://localhost:3000/code-architecture`. Navigate to container level. Verify:
- Containers are not a single vertical column
- Grid is centered horizontally
- Nodes don't overflow viewport excessively

If dagre produces overlapping labels, increase `ranksep` back to 200 and `nodesep` to 130.

- [ ] **Step 3: Run Playwright tests**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run test:e2e 2>&1 | tail -20`

Expected: All pass.

- [ ] **Step 4: Commit**

Run:
```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx
git commit -m "feat(ui): denser container-level graph layout with centered grid"
```
