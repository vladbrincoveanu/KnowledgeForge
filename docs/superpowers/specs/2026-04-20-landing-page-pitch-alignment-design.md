# Landing Page Pitch Alignment — Design Spec

**Date:** 2026-04-20
**Status:** Approved
**Scope:** Replace Pipeline section + redesign Team section

---

## Overview

Align the KnowledgeForge landing page with the narrative in pitch deck slides 5–8. Two changes:

1. Replace the five-step technical pipeline with a three-stage platform narrative (Structure / Intelligence / Judgement)
2. Redesign the Team section to be story-first, matching the pitch's founding voice

---

## Change 1: Replace Pipeline Section

### Before

Five-step technical pipeline: Ingest → Parse → Model → Store → Serve.

### After

**Three-stage platform narrative.**

| Stage | Name | Tagline | Description |
|-------|------|---------|-------------|
| 1 | **Structure** | "Code read directly." | Deterministic extraction. Every service, every dependency, every change — without human mediation. |
| 2 | **Intelligence** | "Senior architect context." | AI enriches the structure with architectural insight. **The AI never modifies the structural foundation.** |
| 3 | **Judgement** | "Human in the loop." | Edge cases routed to a human reviewer. Input is front-loaded and diminishes as the system learns your organisation. |

**Section header:** "How the platform works."
**Section eyebrow:** "Three stages. One source of truth."
**Tagline below stages:** "What an ontology did for enterprise data — we are doing for enterprise software."

### Visual Design

- Three cards in a row (responsive: stacks on mobile)
- Each card: icon + stage name + tagline + description
- Stage 1 icon: `Code2` (blue tint)
- Stage 2 icon: `Sparkles` (indigo tint)
- Stage 3 icon: `UserCheck` (green tint)
- Horizontal connecting line or arrow between cards on desktop

### Data Structure

```typescript
const PLATFORM_STAGES = [
  {
    number: "1",
    name: "Structure",
    tagline: "Code read directly.",
    description: "Deterministic extraction. Every service, every dependency, every change — without human mediation.",
    icon: <Code2 size={24} />,
    color: "blue",
  },
  {
    number: "2",
    name: "Intelligence",
    tagline: "Senior architect context.",
    description: "AI enriches the structure with architectural insight. The AI never modifies the structural foundation.",
    icon: <Sparkles size={24} />,
    color: "indigo",
  },
  {
    number: "3",
    name: "Judgement",
    tagline: "Human in the loop.",
    description: "Edge cases routed to a human reviewer. Input is front-loaded and diminishes as the system learns your organisation.",
    icon: <UserCheck size={24} />,
    color: "green",
  },
];
```

### Placement

Replaces the current `lp-pipeline` section, positioned after the C4 altitude tabs (AltitudeTabSwitcher) and before the Risk Register section.

---

## Change 2: Team Section — Story-First Redesign

### Before

Two founder cards with role/company bios + "Seeking 3 Enterprise Design Partners" ask block.

### After

**Narrative block above cards:**

```
Built by engineers. Run from Vienna.

The product has two layers. A code extraction engine that needs to be precise,
deterministic, and robust at scale — that's one domain. An intelligence layer
on top that needs to be reliable, auditable, and production-grade — that's
the other. We each built half the product before we formalised the company.

We did not start with a pitch deck. We started with the extraction engine —
it runs today, across multiple languages, on real codebases.
```

**Founder cards — sharpened bios:**

| Name | Bio |
|------|-----|
| Iulia Rinea | "Leads data and AI platform work at AI Factory Austria. Production ML infrastructure at scale." |
| Vlad Brincoveanu | "Works in distributed systems at CID. The kind of engineering that sits underneath everything else and cannot afford to fail." |

**Ask block** — unchanged from current design (design partner framing, not Slide 8 asks).

### Data Structure

```typescript
const FOUNDERS = [
  {
    initials: "IR",
    name: "Iulia Rinea",
    title: "Co-founder",
    bio: "Leads data and AI platform work at AI Factory Austria. Production ML infrastructure at scale.",
    email: "rineaiulia17@gmail.com",
    seed: 42,
  },
  {
    initials: "VB",
    name: "Vlad Brincoveanu",
    title: "Co-founder",
    bio: "Works in distributed systems at CID. The kind of engineering that sits underneath everything else and cannot afford to fail.",
    email: "ggvladbrincoveanu@gmail.com",
    seed: 17,
  },
];
```

### Visual Design

- Narrative block: max-width 720px, centered, muted body text, bold lead line "Built by engineers. Run from Vienna."
- Lead line: larger font, gradient text matching hero aesthetic
- Founder cards: unchanged layout, only bio text changes
- Ask block: unchanged

---

## Module Design Blocks

### Module: `PipelineStagesSection` (new)
- **Responsibility:** Replace the five-step pipeline with a three-stage narrative (Structure / Intelligence / Judgement) mirroring the pitch's platform framing
- **Interface:** Static section, reads from `PLATFORM_STAGES` data array
- **Dependencies:** Lucide icons (`Code2`, `Sparkles`, `UserCheck`)
- **Size target:** ~100 lines

### Module: `TeamSection` (updated)
- **Responsibility:** Story-first founder section with sharpened bios and founding narrative copy
- **Interface:** Reads from `FOUNDERS` array + static narrative strings
- **Dependencies:** `GeometricAvatar` (existing)
- **Changes:** Add narrative block above cards, update `bio` strings, keep ask block unchanged

### Module: `FOUNDERS` data (updated)
- **Responsibility:** Founder profile data consumed by `TeamSection`
- **Interface:** Array of `{ initials, name, title, bio, email, seed }`
- **Changes:** `bio` strings rewritten to match pitch voice; no structural change

---

## SCSS Changes

| Selector | Change |
|----------|--------|
| `.lp-pipeline` | Repurposed: from five-step horizontal flow to three-card grid |
| `.lp-pipeline__steps` | Replaced with `.lp-stages__grid` (3-column, gap 1.5rem) |
| `.lp-pipeline__step` | Replaced with `.lp-stage-card` |
| `.lp-stage-card` | New: icon + name + tagline + description, colored top border per stage |
| `.lp-team__narrative` | New block: centered story copy above founder cards |
| `.lp-team__narrative-lead` | New: "Built by engineers. Run from Vienna." — large gradient text |

---

## Responsive Behaviour

- **Desktop (≥1024px):** Three stage cards side-by-side, narrative full-width
- **Tablet (768–1023px):** Three stage cards side-by-side, narrative full-width
- **Mobile (<768px):** Stage cards stack vertically, narrative full-width, founder cards stack

---

## Pre-Delivery Checklist

- [ ] No emojis used as icons (use SVG/Lucide)
- [ ] `cursor-pointer` on all interactive elements
- [ ] Hover states with smooth 200ms transitions
- [ ] `prefers-reduced-motion` respected for stage card animations
- [ ] Responsive at 375px, 768px, 1024px, 1440px
- [ ] No horizontal scroll on mobile
- [ ] Run `npm run test` after implementation
