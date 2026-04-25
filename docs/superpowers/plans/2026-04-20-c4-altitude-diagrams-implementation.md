# C4 Altitude Diagrams — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement.

**Goal:** Fix the three altitude mockup SVGs in the landing page to correctly represent C4 model levels.

**Files:**
- Modify: `landing/src/App.tsx` (MockupView component, lines ~148-275)
- Modify: `landing/src/App.tsx` (ALTITUDES data labels, lines ~51-55)

---

## Task 1: Fix L1 Context (Ecosystem) Mockup

**File:** `landing/src/App.tsx`

**Changes:**
1. Replace `type === "context"` SVG content
2. Show external actors (Customer, Finance Dept) on left
3. Show external systems (Stripe, Salesforce) on right
4. Show KnowledgeForge system boundary with internal containers inside
5. Update label to "L1 · Context View"

```typescript
if (type === "context") {
  const ns = [
    // External actors (left side)
    { cx: 45, cy: 85, label: "Customer", badge: "actor", color: "blue" },
    { cx: 45, cy: 130, label: "Finance", badge: "dept", color: "blue" },
    // External systems (right side)
    { cx: 275, cy: 60, label: "Stripe", badge: "system", color: "indigo" },
    { cx: 275, cy: 115, label: "Salesforce", badge: "system", color: "indigo" },
    // Internal containers (inside system boundary)
    { cx: 120, cy: 75, label: "API Gateway", badge: "container", color: "green" },
    { cx: 180, cy: 75, label: "Scanner", badge: "container", color: "green" },
    { cx: 240, cy: 75, label: "Graph Store", badge: "container", color: "green" },
    { cx: 180, cy: 120, label: "Code Repos", badge: "infra", color: "gray" },
  ];
  const es = [
    [45,85,100,80], [45,130,100,95],  // actors to system
    [250,65,275,65], [250,120,275,120], // system to externals
    [120,75,180,75], [180,75,240,75],  // internal containers
    [180,90,180,105],                   // to repos
  ];
  return (
    <svg viewBox="0 0 320 160" className="mockup-svg" aria-hidden="true">
      {defs}
      <rect width="320" height="160" rx="12" fill="#0a0f1e" />
      <rect width="320" height="160" rx="12" fill="url(#bg-blue)" />
      <rect width="320" height="160" rx="12" fill="url(#grid)" />

      {/* System boundary */}
      <rect x="95" y="40" width="160" height="100" rx="10" fill="none" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="6,3" opacity="0.6"/>
      <text x="175" y="37" textAnchor="middle" fill="#22c55e" fontSize="5" fontFamily="Space Grotesk" fontWeight="600" letterSpacing="0.05em">KNOWLEDGEFORGE</text>

      {/* Render nodes */}
      {ns.map((n,i) => (
        <g key={i}>
          <rect x={n.cx-28} y={n.cy-18} width={56} height={36} rx="8" fill="#0f172a" stroke={n.color === "blue" ? "#3b82f6" : n.color === "indigo" ? "#6366f1" : n.color === "green" ? "#22c55e" : "#4b5563"} strokeWidth="1.2" opacity={n.badge === "actor" || n.badge === "dept" || n.badge === "system" ? 0.7 : 1}/>
          <rect x={n.cx-10} y={n.cy-14} width={20} height={7} rx="2" fill={n.color === "blue" ? "#1e40af" : n.color === "indigo" ? "#4338ca" : n.color === "green" ? "#166534" : "#374151"} opacity="0.8"/>
          <text x={n.cx} y={n.cy-7} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="4" fontFamily="monospace" fontWeight="600">{n.badge?.toUpperCase()}</text>
          <text x={n.cx} y={n.cy+5} textAnchor="middle" fill={n.badge === "actor" || n.badge === "dept" || n.badge === "system" ? "#94a3b8" : "#f1f5f9"} fontSize="6.5" fontFamily="Space Grotesk">{n.label}</text>
        </g>
      ))}

      {/* Render edges */}
      {es.map(([x1,y1,x2,y2],i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#4b5563" strokeWidth="1" strokeDasharray="3,2" opacity="0.6" markerEnd="url(#arr-b)"/>
      ))}

      <rect x="100" y="144" width="120" height="12" rx="6" fill="rgba(30,41,59,0.8)"/>
      <text x="160" y="152.5" textAnchor="middle" fill="#64748b" fontSize="6" fontFamily="Space Grotesk" fontWeight="500">L1 · Context View</text>
    </svg>
  );
}
```

---

## Task 2: Fix L2 Container Mockup

**File:** `landing/src/App.tsx`

**Changes:**
1. Rename label from "L2 · Service View" to "L2 · Container View"
2. Keep services representation but update if needed

---

## Task 3: Fix L3 Component Mockup

**File:** `landing/src/App.tsx`

**Changes:**
1. Rename label from "L3 · Internals View" to "L3 · Component View"
2. Keep the layered architecture (CTRL → SVC → REPO) which is correct

---

## Task 4: Update ALTITUDES Data Labels

**File:** `landing/src/App.tsx`

**Changes:** Update the `ALTITUDES` array labels to match correct C4 terminology:

```typescript
const ALTITUDES = [
  { level: "L1", name: "Context View", persona: "CIO / Board", description: "Your software in context. Focus on business capabilities and regulatory exposure rather than repository names. Identify external integrations and vendor risks that threaten compliance and continuity.", mockup: "context" },
  { level: "L2", name: "Container View", persona: "Architect / Tech Lead", description: "The major moving parts. Map interaction between microservices, containers, and databases. Enable blast-radius simulation for proposed changes before architectural drift compromises integrity.", mockup: "container" },
  { level: "L3", name: "Component View", persona: "Developer / SRE", description: "The real building blocks. Gain immediate clarity on classes, functions, and execution paths. Reduce engineer onboarding from months to hours with deep links back to Git.", mockup: "component" },
];
```

---

## Task 5: Build and Deploy

- [ ] `cd landing && npm run build`
- [ ] `npx vercel --prod`
- [ ] Verify: https://landing-[hash]-vladbrincoveanus-projects.vercel.app

---

## Self-Review Checklist

- [ ] L1 shows external actors/systems outside system boundary, not internal containers
- [ ] L2 labeled "Container View" and shows deployment units
- [ ] L3 labeled "Component View" and shows layered architecture
- [ ] All three views are visually distinct (blue/green/indigo color coding maintained)
- [ ] Build succeeds with no TypeScript errors
