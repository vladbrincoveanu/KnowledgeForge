# Container Edge Rendering Fix — Design Spec

**Date:** 2026-04-19
**Status:** Draft
**Problem:** Container-level edges are invisible in the UI. Context-level diagram also lacks business description labels.

---

## Root Cause Analysis

Two bugs cause container edges to be silently dropped:

### Bug 1 — Name Mismatch

**Location:** `CodeArchitectureViewer.tsx` `generateC4Edges()` lines 129–132

Backend `build_container_relationships()` uses container dictionary keys as relationship `from`/`to` values. Frontend creates `nameToId` from `container.name`. For helm-detected containers these diverge:

- Container `name`: `"omnipay-settlement-orchestrator"` (from `Chart.yaml name:`)
- Relationship `from`: `"settlement-orchestrator"` (from K8s metadata.name in templates)

→ `nameToId.get("settlement-orchestrator")` → `undefined` → edge dropped.

### Bug 2 — Unresolved External Targets

**Location:** Same function, lines 130–132

Most container relationships target infrastructure (PostgreSQL, Redis, Kafka, MongoDB, RabbitMQ) that is **never registered as a container**. Target lookup fails → edge dropped silently.

---

## Fix Strategy

### Fix 1 — Prefix-strip fallback for name mismatch

In `generateC4Edges`, when `sourceId` or `targetId` isn't found, strip the `"omnipay-"` prefix and retry.

### Fix 2 — Link container edges to context-level external nodes

When a container relationship targets an unknown name, check whether it matches a **context-level external dependency** (from `system_context.external_dependencies`). If found, use the **same external entity ID** that context level uses — so both diagram levels show the same external node.

If no match exists in context externals, fall back to an implicit ghost node (dashed border).

### Fix 3 — Business description labels on context level edges

Context-level edges currently show the compact label (from `compactContextEdgeLabel`). Add the **business description** as the full edge label when zoomed in, so users see why we use each external dependency.

---

## Design

### Module: `generateC4Edges`

**Responsibility:** Transform container-level relationships into React Flow edges. Link unresolved targets to context-level external nodes when available; create ghost nodes as fallback.

**Interface:**
- Input: `containers[]`, `relationships[]`, `contextExternalEntities[]`
- Output: `{ nodes: Node[], edges: Edge[] }` — may include new implicit external nodes

**Behavior:**

```
For each relationship:
  1. Resolve sourceId:
     - nameToId.get(sourceName) OR
     - nameToId.get(stripOmniPrefix(sourceName)) OR
     - skip (can't draw from nothing)

  2. Resolve targetId:
     - nameToId.get(targetName) OR
     - nameToId.get(stripOmniPrefix(targetName)) OR
     - contextExternalIdByName.get(targetName) OR          ← NEW: link to context external
     - contextExternalIdByName.get(normalizeName(targetName)) OR  ← strip spaces/dashes
     - create ghost node → return its id                  ← fallback

  3. Emit edge with sourceId → targetId
```

**Ghost node shape:**
```typescript
{
  id: `ghost_external_${sanitize(targetName)}`,
  type: "custom",
  position: { x: ..., y: ... },  // auto-placed by layout
  data: {
    name: targetName,
    entity_type: "external_system",
    attributes: { isGhostExternal: true }
  }
}
```

### Module: `applyArchitecture` (caller)

**Responsibility:** Pass context external entities into `generateC4Edges` so it can link container edges to real context nodes.

**Change:** When calling `generateC4Edges` for container-level, also pass `contextExternalEntities` filtered from `architecture.system_context.external_dependencies`.

```typescript
const contextExternalEntities = (architecture.system_context?.external_dependencies || [])
  .map((dep, idx) => ({
    id: `context_external_${idx}`,
    name: dep.context_name || dep.name,
    entity_type: "external_system",
  }));

const { nodes: containerNodes, edges: containerEdges } = generateC4Edges(
  containerEntities,
  containerRelationships,
  contextExternalEntities,  // ← new third param
);
```

### Module: Implicit Ghost Node Styling

**Responsibility:** Visually distinguish runtime-created external nodes from statically-defined ones.

**CSS class:** `.node-external-ghost`

```scss
.node-external-ghost {
  border: 2px dashed #9ca3af;
  background: #f9fafb;
  opacity: 0.9;

  .node-header {
    background: #6b7280;
    border-bottom: 2px dashed #d1d5db;
  }
}
```

Update `CustomNode.tsx` to check `data.attributes?.isGhostExternal` and apply this class.

### Module: Context-Level Edge Labels

**Responsibility:** Show business descriptions on context-level edges, not just compact labels.

**Change in `edgeRendering.ts` `buildRenderedEdges`:**

For context level, set `label` to the **full description** (not `compactLabel`):

```typescript
label: description || humanizeRelationshipType(relationship.relationship_type),
```

The compact label (`compactContextEdgeLabel`) remains in `data.graph_label` for tooltip/hover. The full description becomes the visible edge label — so when a user hovers over `OmniPay → Stripe` they see "Uses Stripe for payment processing" as the edge label.

### Module: `CustomNode`

**Responsibility:** Render ghost external nodes with dashed border when `isGhostExternal` flag is set.

**Change:** Check `node.data.attributes?.isGhostExternal` → apply `.node-external-ghost` class.

---

## Files to Change

| File | Change |
|------|--------|
| `CodeArchitectureViewer.tsx` | Update `generateC4Edges` signature to accept `contextExternalEntities[]`; implement prefix-strip fallback; link to context externals before creating ghost; pass context externals from `applyArchitecture` |
| `CodeArchitectureViewer.scss` | Add `.node-external-ghost` CSS class |
| `CustomNode.tsx` | Render dashed border when `isGhostExternal` is true |
| `edgeRendering.ts` | Use full `description` as edge label for context level (keep `compactLabel` in `data.graph_label`) |
| `CodeArchitectureViewer.test.tsx` | Add tests for: helm name mismatch, ghost node creation, context external linking |

---

## Test Plan

1. **Unit test** — `generateC4Edges` helm name mismatch: `from: "settlement-orchestrator"` + container `"omnipay-settlement-orchestrator"` → edge created
2. **Unit test** — `generateC4Edges` unresolved `"kafka"` → ghost node + edge created
3. **Unit test** — `generateC4Edges` `"kafka"` with context external `"Kafka"` → links to context external node, no ghost created
4. **Visual** — Load demo app, container level: edges from `omnipay-settlement-orchestrator` to infra visible, edges from containers to context-level externals (Stripe, Auth0) visible
5. **Visual** — Context level: edge labels show full business descriptions

---

## Scope Notes

- Component-level edges: out of scope (separate code path)
- Context-level business labels: in scope (this spec)
- The `c4_architecture.json` cold-start demo will still produce some ghost nodes for infrastructure targets not in `external_dependencies` — this is correct fallback behavior
