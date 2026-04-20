# Landing Page C4 Altitude Diagrams — Design Spec

**Date:** 2026-04-20
**Status:** Approved
**Scope:** Fix the three altitude mockup diagrams on the landing page to correctly represent C4 model levels

---

## Problem

The current altitude switcher on the landing page shows **incorrect C4 levels**:

| Label | Currently Shows | Should Show |
|-------|---------------|-------------|
| L1 "Ecosystem View" | API Gateway, Auth, Postgres, Kafka (internal containers) | External actors + system boundary |
| L2 "Service View" | api-gw, user-svc, pay-svc (microservices) | Containers within the system |
| L3 "Internals View" | main.rs, auth.rs (code files) | Components within a container |

The mislabeled diagrams confuse the pitch — KnowledgeForge extracts all four C4 levels, but the mockups incorrectly show internal architecture at every level.

---

## Correct C4 Model

| Level | Name | Shows | Landing Page |
|-------|------|-------|--------------|
| L1 | Context (Ecosystem) | External actors + system boundary | ✓ Yes |
| L2 | Container (Service) | Applications, services, databases within the system | ✓ Yes |
| L3 | Component (Internals) | Classes/components within a container | ✓ Yes |
| L4 | Code | Actual code files, functions | ✗ No |

---

## L1 — Context (Ecosystem View) Design

**Purpose:** Show KnowledgeForge in context of external actors and neighboring systems. The view that answers "who touches what" for executives and compliance.

### Layout
- Full-width system boundary (dashed green border) containing internal containers
- External actors (Customer, Finance Dept) on left — labeled as human actors
- External systems (Stripe, Salesforce) on right — labeled as external systems
- Internal containers: API Gateway, Code Scanner, AI Enricher, Graph Store, Code Repositories
- Connections showing data flow direction

### Visual Style
- Blue tones for external elements
- Green dashed border for system boundary
- Clean, minimal node style
- "L1 · Context" label at bottom

---

## L2 — Container View Design

**Purpose:** Show the major deployment units within KnowledgeForge. Technology choices + service boundaries + data flow.

### Layout
- API Gateway at top (entry point)
- Three services below: Code Scanner, AI Enricher, Graph Store
- Infrastructure layer at bottom: PostgreSQL, Redis, S3
- Dashed containers grouping related components

### Visual Style
- Green tones (consistent with current theme)
- Each container as a card with name + technology label
- Dashed lines showing data flow
- "L2 · Container View" label at bottom

---

## L3 — Component View Design

**Purpose:** Show the layered architecture inside a single container (Code Scanner). CTRL → SVC → REPO pattern.

### Layout
- Container label at top ("CodeScanner Container")
- Three horizontal layers: Controllers, Services, Repositories
- Color-coded layer badges (CTRL=red, SVC=yellow, REPO=green)
- Vertical connections showing layer-to-layer calls

### Visual Style
- Indigo/purple tones
- Monospace font for code-like elements
- Layer badges for visual hierarchy
- "L3 · Component View" label at bottom

---

## Module Design Block

### Module: `MockupView` (updated)
- **Responsibility:** Renders correct C4 altitude diagrams as inline SVGs
- **Interface:** `type: "context" | "container" | "component"`
- **Dependencies:** None (pure SVG, no external deps)
- **Changes:** Update `type === "context"` to show external actors; update `type === "service"` label to "Container View"; update `type === "internals"` label to "Component View"

---

## Implementation Notes

1. Update `landing/src/App.tsx` — `MockupView` component
2. Keep existing color scheme (blue/green/indigo) for consistency
3. Maintain same SVG viewBox dimensions (320×160) for existing layout
4. Update `ALTITUDES` data array labels if needed
5. Keep all three views as interactive tabs on landing page
