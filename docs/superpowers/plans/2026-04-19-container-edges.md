# Container Edges Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix container-level edges so they appear in the UI. Also show business descriptions on context-level edge labels.

**Architecture:** Three changes: (1) `generateC4Edges` gets smart name resolution + ghost external nodes + returns `{ nodes, edges }`. (2) Call site passes context externals and merges returned nodes. (3) `edgeRendering.buildRenderedEdges` uses full description as context edge label. Ghost nodes rendered via `CustomNode` with dashed border.

**Tech Stack:** React Flow, TypeScript, Vitest, SCSS

---

## Files to Modify

| File | Role |
|------|------|
| `CodeArchitectureViewer.tsx` | Fix `generateC4Edges`, update call site |
| `CustomNode.tsx` | Render ghost nodes with dashed border |
| `CodeArchitectureViewer.scss` | Add `.node-external-ghost` class |
| `edgeRendering.ts` | Use full description as context edge label |
| `CodeArchitectureViewer.test.tsx` | Unit tests for `generateC4Edges` |

---

## Task 1: Rewrite `generateC4Edges` — Smart name resolution + ghost nodes

**Files:** Modify `CodeArchitectureViewer.tsx:108–212`

- [ ] **Step 1: Write the failing test**

```typescript
// Add to CodeArchitectureViewer.test.tsx

describe("generateC4Edges", () => {
  it("resolves helm name mismatch via prefix-strip fallback", () => {
    const containers = [
      { name: "omnipay-settlement-orchestrator", container_type: "Service" },
    ];
    const relationships = [
      { from: "settlement-orchestrator", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const edges = generateC4Edges(containers, relationships, []);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe("container_omnipay-settlement-orchestrator");
    expect(edges[0].target).toBe("ghost_external_kafka");
  });

  it("creates ghost external node when target is unresolved and not in context externals", () => {
    const containers = [
      { name: "omnipay-event-projections" },
    ];
    const relationships = [
      { from: "omnipay-event-projections", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const { nodes, edges } = generateC4Edges(containers, relationships, []);
    expect(edges).toHaveLength(1);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].id).toBe("ghost_external_kafka");
    expect(nodes[0].data.attributes.isGhostExternal).toBe(true);
  });

  it("links to context external node instead of creating ghost when target matches", () => {
    const containers = [
      { name: "omnipay-settlement-orchestrator" },
    ];
    const relationships = [
      { from: "omnipay-settlement-orchestrator", to: "kafka", type: "uses", protocol: "Kafka" },
    ];
    const contextExternals = [
      { id: "context_external_0", name: "kafka", entity_type: "external_system" },
    ];
    const { nodes, edges } = generateC4Edges(containers, relationships, contextExternals);
    expect(edges).toHaveLength(1);
    expect(edges[0].target).toBe("context_external_0");
    expect(nodes).toHaveLength(0); // no ghost created
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd sources/UI && npx vitest run CodeArchitectureViewer.test.tsx`
Expected: FAIL — `generateC4Edges` doesn't return `{ nodes, edges }` yet

- [ ] **Step 3: Rewrite `generateC4Edges`**

Replace the function body (lines 108–212) with:

```typescript
const generateC4Edges = (
  containers: any[] = [],
  relationships: any[] = [],
  contextExternalEntities: any[] = [],
): { nodes: Node[]; edges: Edge[] } => {
  const nameToId = new Map<string, string>();
  containers.forEach((container, idx) => {
    if (container?.name) {
      nameToId.set(container.name, `container_${container.name || idx}`);
    }
  });

  // Build context external name → id lookup (normalise for matching)
  const contextExternalIdByName = new Map<string, string>();
  contextExternalEntities.forEach((ext) => {
    if (ext.name) {
      contextExternalIdByName.set(ext.name.toLowerCase(), ext.id);
      // Also store with spaces/dashes normalised
      const normalised = ext.name.toLowerCase().replace(/[-_\s]+/g, "");
      contextExternalIdByName.set(normalised, ext.id);
    }
  });

  const stripOmniPrefix = (name: string) =>
    name.startsWith("omnipay-") ? name.slice(8) : name;

  const ghostNodes: Node[] = [];
  const edges: Edge[] = [];
  const relationshipEdgesAdded = new Set<string>();

  const resolveId = (
    name: string,
  ): { id: string | null; isGhost: boolean } => {
    if (!name) return { id: null, isGhost: false };
    // 1. Direct container name lookup
    if (nameToId.has(name)) return { id: nameToId.get(name)!, isGhost: false };
    // 2. Strip omnipay- prefix and retry
    const stripped = stripOmniPrefix(name);
    if (nameToId.has(stripped)) return { id: nameToId.get(stripped)!, isGhost: false };
    // 3. Check context externals (direct + normalised)
    const normalised = name.toLowerCase().replace(/[-_\s]+/g, "");
    if (contextExternalIdByName.has(name.toLowerCase()))
      return { id: contextExternalIdByName.get(name.toLowerCase())!, isGhost: false };
    if (contextExternalIdByName.has(normalised))
      return { id: contextExternalIdByName.get(normalised)!, isGhost: false };
    // 4. Create ghost external node
    const ghostId = `ghost_external_${name.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;
    if (!ghostNodes.some((n) => n.id === ghostId)) {
      ghostNodes.push({
        id: ghostId,
        type: "custom",
        position: { x: 0, y: 0 },  // layout will position
        data: {
          label: name,
          type: "external_system",
          displayType: "External",
          isExternal: true,
          attributes: { isGhostExternal: true },
        },
      });
    }
    return { id: ghostId, isGhost: true };
  };

  relationships.forEach((rel, idx) => {
    const sourceName = rel?.from ?? rel?.source;
    const targetName = rel?.to ?? rel?.destination;
    if (!sourceName || !targetName) return;

    const sourceResult = resolveId(String(sourceName));
    const targetResult = resolveId(String(targetName));
    if (!sourceResult.id || !targetResult.id) return;

    const relationshipKey = `${sourceResult.id}-${targetResult.id}`;
    if (relationshipEdgesAdded.has(relationshipKey)) return;

    const protocol =
      typeof rel?.protocol === "string" ? rel.protocol.trim() : "";
    const label = protocol ? protocol.toUpperCase() : undefined;

    edges.push({
      id: `c4-rel-${sourceResult.id}-${targetResult.id}-${idx}`,
      source: sourceResult.id,
      target: targetResult.id,
      label,
      type: "C4Edge",
      interactionWidth: 16,
      markerEnd: { type: MarkerType.ArrowClosed },
      data: {
        description: rel?.description || rel?.llm_description,
        llm_description: rel?.llm_description,
        protocol: protocol || undefined,
        relationship_type: rel?.relationship_type || rel?.type,
      },
    });
    relationshipEdgesAdded.add(relationshipKey);
  });

  // Fallback: build edges from container.dependencies_internal when no relationships given
  if (relationships.length === 0) {
    containers.forEach((container, idx) => {
      const sourceId = `container_${container.name || idx}`;
      const protocol =
        typeof container?.protocol === "string" ? container.protocol.trim() : "";
      const label = protocol ? protocol.toUpperCase() : undefined;
      const deps: string[] = Array.isArray(container?.dependencies_internal)
        ? container.dependencies_internal.map(String)
        : [];

      deps.forEach((depName, depIdx) => {
        const targetResult = resolveId(depName);
        if (!targetResult.id) return;
        const key = `${sourceId}-${targetResult.id}`;
        if (relationshipEdgesAdded.has(key)) return;

        edges.push({
          id: `c4-rel-${sourceId}-${targetResult.id}-${depIdx}`,
          source: sourceId,
          target: targetResult.id,
          label,
          type: "C4Edge",
          interactionWidth: 16,
          markerEnd: { type: MarkerType.ArrowClosed },
          data: { protocol, relationship_type: "uses" },
        });
        relationshipEdgesAdded.add(key);
      });
    });
  }

  return { nodes: ghostNodes, edges };
};
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd sources/UI && npx vitest run CodeArchitectureViewer.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.test.tsx
git commit -m "test: add generateC4Edges unit tests for name mismatch, ghost nodes, context external linking"
```

---

## Task 2: Update `applyArchitecture` call site to pass context externals and merge nodes

**Files:** Modify `CodeArchitectureViewer.tsx:2101–2109`

- [ ] **Step 1: Update call site**

Replace lines 2101–2109:

```typescript
    // Build context external entities from system_context for linking
    const contextExternalEntities = (
      architecture.system_context?.external_dependencies || []
    ).map((dep: any, idx: number) => ({
      id: `context_external_${idx}`,
      name: dep.context_name || dep.name,
      entity_type: "external_system",
    }));

    const { nodes: ghostNodes, edges: dependencyEdges } =
      selectedLevel === "container_level" &&
      (architecture?.containers?.length > 0 ||
        (architecture?.relationships?.containers?.length ?? 0) > 0)
        ? generateC4Edges(
            architecture?.containers || [],
            architecture?.relationships?.containers || [],
            contextExternalEntities,
          )
        : { nodes: [], edges: [] };
```

Then update `mergedEdges` to include `ghostNodes`:

```typescript
    const mergedEdges = [...rfEdges, ...dependencyEdges];
    const mergedNodes = [...rfNodes, ...ghostNodes];
```

Update the layout call to use `mergedNodes`:

```typescript
    if (selectedLevel === "context_level") {
      layoutedNodes = layoutContextLevel([...mergedNodes]);
      layoutedEdges = mergedEdges;
    } else {
      const result = getLayoutedElements(mergedNodes, mergedEdges);
      layoutedNodes = result.nodes;
      layoutedEdges = result.edges;
    }
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `cd sources/UI && npx vitest run CodeArchitectureViewer.test.tsx`
Expected: PASS (all 14 existing tests still pass)

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx
git commit -m "fix: update generateC4Edges call site with context externals and ghost node merging"
```

---

## Task 3: Render ghost external nodes with dashed border in `CustomNode`

**Files:** Modify `CustomNode.tsx`

- [ ] **Step 1: Update `CustomNode` to handle ghost external nodes**

In the `CustomNode` component, find the C4-style rendering block (lines 189–233) and add ghost detection:

```typescript
const CustomNode: React.FC<CustomNodeProps> = ({ data }) => {
  // ... existing code ...

  // Determine if this is a ghost external node
  const isGhostExternal = data.attributes?.isGhostExternal === true;

  return (
    <div
      className={`react-flow__node-custom node-type-${data.type}${
        isGhostExternal ? " node-external-ghost" : ""
      }`}
      style={
        isGhostExternal
          ? {
              border: "2px dashed #9ca3af",
              background: "#f9fafb",
              opacity: 0.9,
            }
          : isC4
          ? { background: bg, color, borderColor: bg }
          : undefined
      }
    >
```

Also update the non-container C4 node path to pass through the ghost styling:

```typescript
  return (
    <div
      className={`react-flow__node-custom node-type-${data.type}${
        isGhostExternal ? " node-external-ghost" : ""
      }`}
      style={
        isGhostExternal
          ? { border: "2px dashed #9ca3af", background: "#f9fafb", opacity: 0.9 }
          : isC4
          ? { background: bg, color, borderColor: bg }
          : undefined
      }
    >
```

Also update the container path (lines 147–186) to support ghost container externals:

```typescript
    if (isContainer && data.containerMeta) {
      // ...
      return (
        <div
          className={`react-flow__node-custom node-type-container${
            isGhostExternal ? " node-external-ghost" : ""
          }`}
          style={{
            borderColor: isGhostExternal ? "#9ca3af" : catStyle.borderColor,
            background: isGhostExternal ? "#f9fafb" : catStyle.bodyBg,
            border: isGhostExternal ? "2px dashed #9ca3af" : undefined,
            opacity: isGhostExternal ? 0.9 : 1,
          }}
        >
```

- [ ] **Step 2: Run tests**

Run: `cd sources/UI && npx vitest run`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CustomNode.tsx
git commit -m "feat: render ghost external nodes with dashed border"
```

---

## Task 4: Add `.node-external-ghost` CSS class

**Files:** Modify `CodeArchitectureViewer.scss`

- [ ] **Step 1: Add ghost node styles at the end of the file**

```scss
// Ghost external nodes (created at runtime for unresolved relationship targets)
.node-external-ghost {
  border: 2px dashed #9ca3af !important;
  background: #f9fafb;
  opacity: 0.9;

  .node-header {
    background: #6b7280;
    border-bottom: 2px dashed #d1d5db;
  }

  .node-content {
    background: #f9fafb;
  }
}
```

- [ ] **Step 2: Run tests**

Run: `cd sources/UI && npx vitest run`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss
git commit -m "style: add node-external-ghost CSS for unresolved external nodes"
```

---

## Task 5: Show full business description on context-level edge labels

**Files:** Modify `edgeRendering.ts:190`

- [ ] **Step 1: Change context-level edge label to use full description**

In `buildRenderedEdges`, find line 190:
```typescript
label: isContextLevel ? compactLabel || description : undefined,
```

Change to:
```typescript
label: description || compactLabel || humanizeRelationshipType(relationship.relationship_type),
```

The `compactLabel` is kept in `data.graph_label` (line 200) for tooltip/hover use.

- [ ] **Step 2: Run edge rendering tests**

Run: `cd sources/UI && npx vitest run edgeRendering.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/edgeRendering.ts
git commit -m "feat: show full business description as edge label on context level"
```

---

## Task 6: Add `edgeRendering` test for context-level full description label

**Files:** Modify `edgeRendering.test.ts`

- [ ] **Step 1: Add test for full description as context-level label**

Add to `edgeRendering.test.ts`:

```typescript
test("uses full description as label for context level edges", () => {
  const edges = buildRenderedEdges(
    [
      {
        source_entity_id: "system",
        target_entity_id: "stripe",
        relationship_type: "uses",
        attributes: {
          description: "Uses Stripe for payment processing and subscriptions",
        },
      },
    ],
    true, // isContextLevel
    [
      { id: "system", name: "OmniPay", entity_type: "system" },
      { id: "stripe", name: "Stripe", entity_type: "external_service" },
    ],
  );

  expect(edges).toHaveLength(1);
  // Full description, not compact label
  expect(edges[0].label).toBe("Uses Stripe for payment processing and subscriptions");
  // Compact version still in data for tooltip
  expect(edges[0].data.graph_label).toBe("Uses Stripe for payment");
});
```

- [ ] **Step 2: Run tests**

Run: `cd sources/UI && npx vitest run edgeRendering.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/architecture-map/CodeArchitectureViewer/edgeRendering.test.ts
git commit -m "test: add context-level full description edge label test"
```

---

## Task 7: Full integration — run all tests

- [ ] **Step 1: Run full frontend test suite**

Run: `cd sources/UI && npx vitest run`
Expected: ALL tests PASS (50+ tests)

- [ ] **Step 2: Commit remaining changes**

```bash
git add -A
git commit -m "feat: container edge rendering with ghost external nodes and context-level business labels"
```

---

## Spec Coverage Checklist

- [x] Bug 1 (name mismatch) — Task 1: prefix-strip fallback
- [x] Bug 2 (unresolved external targets) — Task 1: ghost node creation
- [x] Link to context externals — Task 1: `contextExternalIdByName` lookup
- [x] Merge ghost nodes into graph — Task 2: call site update with `ghostNodes`
- [x] Ghost node rendering — Task 3: `CustomNode` with dashed border
- [x] Ghost node CSS — Task 4: `.node-external-ghost` class
- [x] Context-level business labels — Task 5: full description as edge label
- [x] Unit tests for `generateC4Edges` — Task 1
- [x] Integration tests — Task 6
