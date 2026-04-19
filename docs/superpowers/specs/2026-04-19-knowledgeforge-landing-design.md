# KnowledgeForge Landing Page — Design Spec
**Date:** 2026-04-19
**Status:** Approved for Implementation
**Revision:** 2 (Spaced & Premium + Visual Premium Direction)

---

## 1. Concept & Vision

KnowledgeForge is "The operating system for your software estate." The landing page must feel like mission control — dark, intelligent, alive. Every section communicates this is not a documentation tool but the fundamental infrastructure that bridges ground-truth engineering and boardroom strategy. The page is aspirational for CTOs/CIOs and credible for engineers.

**Direction chosen:** Option B — Spaced & Premium. Generous breathing room, centered single-column hero, large typography, enhanced visual depth.

---

## 2. Design Language

### Aesthetic Direction
**"Trust & Authority" dark tech** — inspired by Bloomberg Terminal meets Vercel dashboard. Slate-navy backgrounds, emerald-green CTAs, no playful elements, no AI-pink gradients. Clean, data-dense, premium.

### Visual Premium Enhancements
- Rich layered gradient backgrounds with ambient glow orbs
- Cards with subtle inner shadow depth and backdrop blur
- Founder avatars: custom geometric/illustrated style (no photos)
- Product mockups: higher-fidelity wireframes with UI chrome and depth
- Enhanced hero graph with glow filters and vignette overlay
- Warmer dark palette with more depth variation

### Color Palette
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Background | `#0F172A` | `--lp-bg` |
| Primary | `#1E293B` | `--lp-primary` |
| Secondary | `#334155` | `--lp-secondary` |
| CTA | `#22C55E` | `--lp-cta` |
| CTA Hover | `#16A34A` | `--lp-cta-hover` |
| Text | `#F8FAFC` | `--lp-text` |
| Muted text | `#94A3B8` | `--lp-muted` |
| Graph nodes | `#3B82F6` | `--lp-node` |
| Graph edges | `#1E40AF` | `--lp-edge` |
| Border | `rgba(255,255,255,0.08)` | `--lp-border` |
| Border Hover | `rgba(255,255,255,0.16)` | `--lp-border-hover` |
| Card bg | `rgba(30,41,59,0.6)` | `--lp-card` |
| Card solid | `#1E293B` | `--lp-card-solid` |
| Glow | `rgba(59,130,246,0.15)` | `--lp-glow` |

### Typography
- **Font:** Plus Jakarta Sans (Google Fonts), weights 300/400/500/600/700
- **H1:** 700, `clamp(3rem, 5vw, 4.5rem)`, line-height 1.0, tracking -0.03em
- **H2:** 700, `clamp(2rem, 3.5vw, 3rem)`, line-height 1.05
- **H3:** 600, 1.25rem
- **Body:** 400, 1rem, line-height 1.7
- **Eyebrow:** 700, 0.75rem, uppercase, letter-spacing 0.1em

### Spatial System (Option B — Spaced & Premium)
- Section padding: 5rem vertical (desktop), 4rem (tablet), 3rem (mobile)
- Hero padding: 8rem top, generous bottom padding
- Card border-radius: 16px
- Button border-radius: 999px (pill)
- Grid gap: 1.5rem desktop, tighter on mobile
- Max-width: 1280px centered

### Motion Philosophy
- **Micro-interactions:** 200ms ease for hovers/focus
- **Stat reveals:** Staggered fade-up on scroll into view
- **Hero graph:** CSS keyframe animations — nodes drift (20–40s cycle), edges pulse opacity (4s cycle)
- **Aurora drift:** Slow ambient gradient animation (18s ease-in-out alternate)
- **Tab switch:** 200ms crossfade between altitude panels
- **No layout-shifting transforms** on hover
- **prefers-reduced-motion** respected on all animations

### Visual Assets
- **Icons:** Lucide React (consistent 24x24, stroke-width 1.5)
- **Hero graph:** Inline animated SVG with ~32 nodes, glow filters, vignette overlay
- **Founder avatars:** Custom illustrated/geometric style in brand colors (navy + blue gradient circles with abstract interior patterns)
- **No external images** — all visuals are CSS/SVG/inline
- **Background:** Radial gradient mesh overlays on hero and CTA sections

---

## 3. Page Structure

### Navbar (fixed, floating)
Logo left | Nav links center | "Contact Sales" ghost + "Login" text right
- Floating with rounded corners + backdrop blur
- States: default (transparent-ish), no scrolled variant needed

### Section 1 — Hero (full viewport height, centered variant)
- **Centered single-column layout** with max-width constraint
- Eyebrow + H1 + subhead + dual CTA buttons + trust note
- Full-width animated SVG node-link graph below text
- Aurora mesh gradient animation as background layer

### Section 2 — The Stakes (dark card strip)
Three stat cards in a row: 30% IT Budget Waste | $6T Global Tech Debt | $4.88M Per Data Breach

### Section 3 — The Two Audiences
Two-column layout:
- Left: "The Operator's Blind Spot" (Engineering) — 4 pain points
- Right: "The Commander's Blind Spot" (Leadership) — 4 pain points

### Section 4 — The Solution
Section header + 4 pillar cards: No Manual Diagrams | Self-Updating | Quarriable Altitudes | One Source of Truth

### Section 5 — The Product: Three Altitudes (tab switcher)
- L1 / L2 / L3 tab bar
- Active tab: emerald underline indicator
- Below tabs: altitude detail card (name, persona badge, description, enhanced mockup preview)

### Section 6 — The Engine
5-step pipeline row: Ingest → Parse → Model → Store → Serve
Each step: number badge + name + one-line description

### Section 7 — The Risk Register
4 cards: Key-Person Risk | Supply-Chain Risk | Technical Debt | Lifecycle Waste

### Section 8 — The Ask
Two founder cards side by side (Iulia Rinea, Vlad Brincoveanu) with geometric illustrated avatars and email CTAs

### Footer
Simple dark bar: © 2026 KnowledgeForge

---

## 4. Component Inventory

### `<LandingPage>` (root)
- Manages active tab state for altitude switcher
- Renders all sections in order

### `<Navbar>`
- Fixed position, floating with rounded corners + backdrop blur
- Logo with hexagonal KnowledgeForge SVG mark

### `<HeroSection>`
- Centered layout with max-width
- Eyebrow tag + H1 + subhead + dual CTAs + trust note
- Full-width `<AnimatedGraphCanvas>` with aurora background layer

### `<AnimatedGraphCanvas>`
- Inline SVG, 32 nodes, ~40 edges
- CSS animations: node drift + edge pulse
- `will-change: transform` on nodes for perf
- Glow filter on nodes, vignette overlay
- `prefers-reduced-motion` respected

### `<StatCard>`
- Large metric number, label, source
- Subtle blue radial glow on hover

### `<BlindSpotCard>`
- Title + 4 pain-point list items with icons
- Distinct accent per column (blue vs slate)

### `<PillarCard>`
- Icon (Lucide) + title + description
- 4 across on desktop, 2 on tablet, 1 on mobile

### `<AltitudeTabSwitcher>`
- Tab bar (L1/L2/L3)
- Active tab: emerald underline
- Detail panel with crossfade transition
- Enhanced mockup view with more detail and depth

### `<MockupView>`
- L1: Context-level C4 diagram with glow halos and UI chrome
- L2: Service-level diagram with emerald accent and depth layers
- L3: Code internals with monospace nodes and indigo accent
- All: Grid pattern background, ambient glow ellipse, vignette

### `<PipelineStep>`
- Number badge (emerald circle) + step name + description
- Arrow connector between steps

### `<RiskCard>`
- Risk name + stat + explanation
- Hover: subtle glow increase

### `<FounderCard>`
- **Geometric illustrated avatar**: Gradient circle (#3B82F6 → #6366F1) with abstract interior geometric pattern (hexagonal network lines in white at low opacity)
- Name + title + bio
- "Email [Name]" emerald pill button

### `<Footer>`
- Copyright + links

---

## 5. Technical Approach

- **Stack:** React + TypeScript + SCSS (existing project)
- **Fonts:** Google Fonts CDN (Plus Jakarta Sans)
- **Icons:** Lucide React (already installed)
- **No external image deps** — all visuals are CSS/SVG/inline
- **Responsive breakpoints:** 768px (tablet), 1024px (desktop)
- **Accessibility:** semantic HTML, focus-visible states, aria-labels on icon-only buttons

### Module Design Blocks

#### Module: LandingPage (root)
- **Responsibility:** Orchestrates all sections, manages altitude tab state
- **Interface:** No props, renders full page
- **Dependencies:** React, all section components, SCSS

#### Module: AnimatedGraphCanvas
- **Responsibility:** Deterministic animated SVG node-edge graph for hero
- **Interface:** No props, pure presentation
- **Dependencies:** React, seededRandom, GRAPH_NODES/GRAPH_EDGES constants

#### Module: MockupView
- **Responsibility:** Renders L1/L2/L3 altitude wireframe mockups as inline SVG
- **Interface:** `type: "context" | "service" | "code"`
- **Dependencies:** React, useMemo for SVG defs

#### Module: FounderCard
- **Responsibility:** Founder info with geometric avatar illustration
- **Interface:** `founder: { initials, name, title, bio, email }`
- **Dependencies:** React, Lucide ArrowRight, CSS avatar styling
