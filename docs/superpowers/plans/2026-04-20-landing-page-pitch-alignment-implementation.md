# Landing Page Pitch Alignment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five-step pipeline section with a three-stage platform narrative (Structure/Intelligence/Judgement), and redesign the Team section with story-first founding narrative and sharpened bios.

**Architecture:** Two targeted changes to an existing React/TypeScript landing page. No new dependencies. New component `PipelineStagesSection` replaces `PipelineSection`. `TeamSection` gets a new narrative sub-block and updated data. All styles live in the existing SCSS file using CSS custom properties already defined on `.lp-page`.

**Tech Stack:** React 18, TypeScript, SCSS, Lucide React icons

**Files:**
- Modify: `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`
- Modify: `sources/UI/src/@components/landing/LandingPage/LandingPage.scss`

---

## File Map

```
LandingPage.tsx
├── PLATFORM_STAGES data array (new)
├── FOUNDERS data array (bio text update)
├── PipelineStagesSection component (new, replaces PipelineSection)
└── TeamSection component (adds narrative block)
    └── GeometricAvatar (existing, unchanged)

LandingPage.scss
├── .lp-stages__grid (new, replaces .lp-pipeline__steps)
├── .lp-stage-card (new, replaces .lp-pipeline__step)
├── .lp-stage-card--blue/--indigo/--green (new color variants)
└── .lp-team__narrative + .lp-team__narrative-lead (new)
```

---

## Task 1: Add PLATFORM_STAGES Data and Import New Icons

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`

**Changes:**
- Add `Sparkles` and `UserCheck` to the existing Lucide import block (line 1–28)
- Add the `PLATFORM_STAGES` constant after the `PIPELINE_STEPS` constant (after line 187)

- [ ] **Step 1: Add imports**

Find line 1–28. Add `Sparkles` and `UserCheck` to the import list:

```typescript
import {
  AlarmClock,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  CheckCircle2,
  Code2,
  Database,
  Download,
  Eye,
  FileText,
  GitBranch,
  Globe,
  HardDrive,
  Layers,
  Link2,
  MessageCircle,
  Monitor,
  Network,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  UserCheck,
  Users2,
  XCircle,
} from "lucide-react";
```

- [ ] **Step 2: Add PLATFORM_STAGES data array after PIPELINE_STEPS (after line 187)**

```typescript
const PLATFORM_STAGES = [
  {
    number: "1",
    name: "Structure",
    tagline: "Code read directly.",
    description:
      "Deterministic extraction. Every service, every dependency, every change — without human mediation.",
    icon: <Code2 size={24} />,
    color: "blue",
  },
  {
    number: "2",
    name: "Intelligence",
    tagline: "Senior architect context.",
    description:
      "AI enriches the structure with architectural insight. The AI never modifies the structural foundation.",
    icon: <Sparkles size={24} />,
    color: "indigo",
  },
  {
    number: "3",
    name: "Judgement",
    tagline: "Human in the loop.",
    description:
      "Edge cases routed to a human reviewer. Input is front-loaded and diminishes as the system learns your organisation.",
    icon: <UserCheck size={24} />,
    color: "green",
  },
];
```

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.tsx
git commit -m "feat(landing): add PLATFORM_STAGES data and new icon imports

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
"
```

---

## Task 2: Build PipelineStagesSection Component

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`

**Placement:** Add after the existing `PipelineSection` component definition (around line 1237). The component uses a `StageCard` sub-component.

- [ ] **Step 1: Write the PipelineStagesSection component after PipelineSection (line 1237)**

```typescript
const StageCard: React.FC<(typeof PLATFORM_STAGES)[number]> = ({
  number,
  name,
  tagline,
  description,
  icon,
  color,
}) => (
  <article className={`lp-stage-card lp-stage-card--${color}`}>
    <div className="lp-stage-card__header">
      <span className="lp-stage-card__number">{number}</span>
      <span className={`lp-stage-card__icon lp-stage-card__icon--${color}`}>
        {icon}
      </span>
    </div>
    <h3 className="lp-stage-card__name">{name}</h3>
    <p className="lp-stage-card__tagline">{tagline}</p>
    <p className="lp-stage-card__description">{description}</p>
  </article>
);

const PipelineStagesSection: React.FC = () => (
  <section className="lp-pipeline" aria-label="How the platform works">
    <div className="lp-section-header">
      <span className="lp-eyebrow">Three stages. One source of truth.</span>
      <h2>How the platform works.</h2>
      <p>
        What an ontology did for enterprise data — we are doing for enterprise
        software.
      </p>
    </div>
    <div className="lp-stages__grid">
      {PLATFORM_STAGES.map((stage) => (
        <StageCard key={stage.number} {...stage} />
      ))}
    </div>
  </section>
);
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.tsx
git commit -m "feat(landing): add PipelineStagesSection component with three-stage cards

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 3: Replace PipelineSection with PipelineStagesSection in LandingPage

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`

- [ ] **Step 1: Find the PipelineSection component call and replace it**

Find this in the `LandingPage` component (around line 1459):

```tsx
{/* ── PIPELINE ── */}
<PipelineSection />
```

Replace with:

```tsx
{/* ── THREE-STAGE PLATFORM ── */}
<PipelineStagesSection />
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.tsx
git commit -m "feat(landing): replace PipelineSection with PipelineStagesSection

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 4: Add SCSS for Stage Cards

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.scss`

**Changes:** Add `.lp-stages__grid` and `.lp-stage-card` styles, then remove/repurpose old `.lp-pipeline__steps` and `.lp-pipeline__step` rules.

- [ ] **Step 1: Find the `.lp-pipeline` block (line 878) and replace its inner content**

Replace the entire `.lp-pipeline` block content (keeping the outer `.lp-pipeline` selector but replacing what's inside):

```scss
/* ── THREE-STAGE PLATFORM ─────────────────────────────────────────────────── */
.lp-pipeline {
  padding: var(--lp-section-py) 0;
  background: radial-gradient(
    ellipse 50% 60% at 50% 50%,
    rgba(30, 64, 175, 0.08) 0%,
    transparent 70%
  );
  background-color: var(--lp-bg);

  .lp-section-header {
    margin-bottom: 3rem;
  }
}

.lp-stages__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-top: 0;
}

.lp-stage-card {
  padding: 2rem 1.75rem;
  border-radius: var(--lp-radius-lg);
  background: var(--lp-card);
  border: 1px solid var(--lp-border);
  border-top-width: 3px;
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition:
    border-color 200ms ease,
    box-shadow 250ms ease,
    transform 200ms ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow:
      0 8px 24px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  &--blue {
    border-top-color: var(--lp-node);
    &:hover {
      border-top-color: #60a5fa;
      box-shadow:
        0 8px 24px rgba(59, 130, 246, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
  }
  &--indigo {
    border-top-color: #6366f1;
    &:hover {
      border-top-color: #818cf8;
      box-shadow:
        0 8px 24px rgba(99, 102, 241, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
  }
  &--green {
    border-top-color: var(--lp-cta);
    &:hover {
      border-top-color: #4ade80;
      box-shadow:
        0 8px 24px rgba(34, 197, 94, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.25rem;
  }

  &__number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--lp-border);
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--lp-muted);
  }

  &__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.75rem;
    height: 2.75rem;
    border-radius: var(--lp-radius-sm);

    &--blue {
      background: rgba(59, 130, 246, 0.1);
      color: var(--lp-node);
      border: 1px solid rgba(59, 130, 246, 0.2);
    }
    &--indigo {
      background: rgba(99, 102, 241, 0.1);
      color: #6366f1;
      border: 1px solid rgba(99, 102, 241, 0.2);
    }
    &--green {
      background: rgba(34, 197, 94, 0.1);
      color: var(--lp-cta);
      border: 1px solid rgba(34, 197, 94, 0.2);
    }
  }

  &__name {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0 0 0.4rem;
    letter-spacing: -0.01em;
  }

  &__tagline {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--lp-muted);
    margin: 0 0 0.85rem;
    line-height: 1.4;
  }

  &__description {
    font-size: 0.88rem;
    color: var(--lp-muted);
    line-height: 1.65;
    margin: 0;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.scss
git commit -m "feat(landing): add .lp-stage-card and .lp-stages__grid SCSS

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 5: Update FOUNDERS Data with Sharpened Bios

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`

- [ ] **Step 1: Update FOUNDERS bio strings**

Find the `FOUNDERS` array (around line 220). Replace the `bio` values:

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

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.tsx
git commit -m "feat(landing): sharpen founder bios to match pitch voice

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 6: Add Narrative Block to TeamSection

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.tsx`

- [ ] **Step 1: Find TeamSection (around line 1263) and add narrative block before the founder cards**

Find the `lp-team__grid` div inside `TeamSection`. Add the narrative block immediately before it:

```typescript
const TeamSection: React.FC = () => (
  <section className="lp-team" id="partners" aria-label="Founders">
    <div className="lp-section-header">
      <span className="lp-eyebrow">The Team</span>
      <h2>Built by engineers who've lived this.</h2>
      <p>
        We understand the modernization pressure facing platform leaders because
        we have lived it. No consultants — just practitioners.
      </p>
    </div>

    {/* ── FOUNDING NARRATIVE ── */}
    <div className="lp-team__narrative">
      <p className="lp-team__narrative-lead">Built by engineers. Run from Vienna.</p>
      <p className="lp-team__narrative-body">
        The product has two layers. A code extraction engine that needs to be
        precise, deterministic, and robust at scale — that&apos;s one domain. An
        intelligence layer on top that needs to be reliable, auditable, and
        production-grade — that&apos;s the other. We each built half the product
        before we formalised the company.
      </p>
      <p className="lp-team__narrative-body">
        We did not start with a pitch deck. We started with the extraction
        engine — it runs today, across multiple languages, on real codebases.
      </p>
    </div>

    <div className="lp-team__grid">
      {FOUNDERS.map((founder) => (
        <article key={founder.name} className="lp-founder-card">
          <div className="lp-founder-card__avatar">
            <GeometricAvatar initials={founder.initials} seed={founder.seed} />
          </div>
          <div className="lp-founder-card__info">
            <h3>{founder.name}</h3>
            <span className="lp-founder-card__title">{founder.title}</span>
            <p>{founder.bio}</p>
          </div>
          <a
            href={`mailto:${founder.email}`}
            className="lp-btn lp-btn--primary lp-btn--pill lp-founder-card__cta"
          >
            <span>Email {founder.name.split(" ")[0]}</span>
            <ArrowRight size={14} />
          </a>
        </article>
      ))}
    </div>

    {/* ── ASK BLOCK (unchanged) ── */}
    <div className="lp-ask-block">
      <h2>Seeking 3 Enterprise Design Partners</h2>
      <div className="lp-ask-block__perks">
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Free pilot deployment for one repository cluster</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Weekly co-development with founders</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>First-partner pricing locked for 24 months</span>
        </div>
      </div>
      <div className="lp-ask-block__cta">
        <a href="#partners" className="lp-btn lp-btn--primary lp-btn--pill">
          <span>Request Pilot Access</span>
          <ArrowRight size={16} />
        </a>
      </div>
    </div>
  </section>
);
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.tsx
git commit -m "feat(landing): add story-first narrative block to TeamSection

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 7: Add SCSS for Team Narrative Block

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.scss`

- [ ] **Step 1: Find `.lp-team` block (line 1032) and add narrative styles before `__grid`**

Insert inside `.lp-team` block, before the existing `&__grid` rule:

```scss
  &__narrative {
    max-width: 720px;
    margin: 0 auto 3rem;
    text-align: center;
  }

  &__narrative-lead {
    font-size: clamp(1.4rem, 2.5vw, 2rem);
    font-weight: 700;
    margin: 0 0 1.25rem;
    letter-spacing: -0.025em;
    background: linear-gradient(135deg, #f8fafc 0%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  &__narrative-body {
    font-size: 1rem;
    color: var(--lp-muted);
    line-height: 1.75;
    margin: 0 0 1rem;
    max-width: 60ch;
    margin-left: auto;
    margin-right: auto;

    &:last-child {
      margin-bottom: 0;
    }
  }
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.scss
git commit -m "feat(landing): add .lp-team__narrative SCSS styles

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 8: Responsive Overrides for Stage Cards and Narrative

**File:** `sources/UI/src/@components/landing/LandingPage/LandingPage.scss`

- [ ] **Step 1: Find the `@media (max-width: 1024px)` block and add stage grid override**

After the existing `.lp-pipeline__item` width rule inside the 1024px breakpoint, add:

```scss
  .lp-stages__grid {
    grid-template-columns: 1fr 1fr;
  }
```

Then in the `@media (max-width: 768px)` block, add:

```scss
  .lp-stages__grid {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 2: Commit**

```bash
git add sources/UI/src/@components/landing/LandingPage/LandingPage.scss
git commit -m "feat(landing): add responsive breakpoints for stage card grid

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
"
```

---

## Task 9: Run Tests

- [ ] **Step 1: Run frontend tests**

```bash
cd sources/UI && npm run test
```

Expected: All tests pass.

- [ ] **Step 2: Run lint/format check**

```bash
cd sources/UI && npm run check-all
```

Expected: No errors.

---

## Self-Review Checklist

- [ ] Spec coverage: Both changes (pipeline replacement + team redesign) are fully covered by tasks
- [ ] No placeholders: All code is complete, no "TODO", "TBD", or vague descriptions
- [ ] Type consistency: `PLATFORM_STAGES` array typed correctly, `StageCard` props match array element type
- [ ] All 7 commits cover all changes
- [ ] Old `.lp-pipeline__step` and `.lp-pipeline__steps` rules still exist but are unused (harmless, no need to remove)
- [ ] `Sparkles` and `UserCheck` imported and used exactly once each
