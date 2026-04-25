# Skill Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ui-ux-pro-max auto-invoke whenever the brainstorming skill detects UI context, using a hard-rule (always invoke, no user prompt).

**Architecture:** Edit the brainstorming skill's preamble to detect UI keywords and run the design system search with `--persist`. Create a design-system directory for output.

**Tech Stack:** Bash, Python, existing ui-ux-pro-max skill

---

## File Map

```
.claude/skills/
  ui-ux-pro-max/                    # EXISTING — skill already installed
    scripts/
      search.py                     # EXISTING — --design-system --persist flag

.claude/
  skills/
    superpowers-brainstorm-auto.sh  # NEW — UI context detection + search runner
    # AND: modify the superpowers:brainstorming skill description to add the auto-invoke preamble

design-system/
  MASTER.md                          # GENERATED — by ui-ux-pro-max search
  pages/
    knowledgeforge-architecture-viewer.md  # NEW — page-specific overrides
```

---

## Step 0: Verify ui-ux-pro-max is accessible

**Files:**
- Check: `.claude/skills/ui-ux-pro-max/scripts/search.py`

- [ ] **Step 1: Verify the script exists and works**

```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py --help 2>&1 | head -5
```

Expected: Help text (no error)

---

## Step 1: Create the auto-invoke script

**Files:**
- Create: `.claude/skills/superpowers-brainstorm-auto.sh`

- [ ] **Step 1: Create the script**

```bash
mkdir -p .claude/skills
touch .claude/skills/superpowers-brainstorm-auto.sh
chmod +x .claude/skills/superpowers-brainstorm-auto.sh
```

```bash
#!/usr/bin/env bash
# superpowers-brainstorm-auto.sh
# Runs ui-ux-pro-max design system search when UI context is detected.
# Called by the brainstorming skill preamble.

set -e

UI_KEYWORDS="ui|ux|component|layout|button|color|typography|palette|font|spacing|accessibility|tooltip|panel|sidebar|graph|visual|design|style|professional|enterprise|dashboard|mockup|wireframe|prototype|interface|frontend"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Check if stdin or args contain UI keywords
input_text=$(cat "${1:-/dev/stdin}" 2>/dev/null || echo "")

if echo "$input_text" | grep -iqE "$UI_KEYWORDS"; then
  echo "[superpowers] UI context detected — running ui-ux-pro-max..."

  cd "$PROJECT_ROOT"

  # Run design system search and persist
  python3 "$SKILL_DIR/ui-ux-pro-max/scripts/search.py" \
    "enterprise dashboard architecture visualization" \
    --design-system \
    --persist \
    -p "KnowledgeForge" \
    -f markdown \
    2>/dev/null || true

  echo "[superpowers] Design system updated at design-system/MASTER.md"
fi
```

- [ ] **Step 2: Make it executable and test with a UI keyword**

```bash
chmod +x .claude/skills/superpowers-brainstorm-auto.sh
echo "make the UI better" | .claude/skills/superpowers-brainstorm-auto.sh /dev/stdin
```

Expected: Script runs, tries to call search.py, creates design-system/MASTER.md (or skips gracefully if Python env not set up)

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/superpowers-brainstorm-auto.sh
git commit -m "feat(skill): add ui-ux-pro-max auto-invoke script"
```

---

## Step 2: Integrate into brainstorming skill preamble

**Files:**
- Modify: The `superpowers:brainstorming` skill description (via the Skill tool)

**How to modify:** The brainstorming skill's description contains instructions. Add this block at the very top of the skill's preamble:

```
## UI Context Auto-Detection (HARD RULE)
Before processing ANY request, scan the user's prompt for these UI keywords:
  ui, ux, component, layout, button, color, typography, palette, font,
  spacing, accessibility, tooltip, panel, sidebar, graph, visual, design,
  style, professional, enterprise, dashboard, mockup, wireframe, frontend

If ANY keyword is found:
1. FIRST: Run `python3 .claude/skills/ui-ux-pro-max/scripts/search.py \
     "enterprise dashboard architecture visualization" \
     --design-system --persist -p "KnowledgeForge" -f markdown`
2. Read the resulting design-system/MASTER.md
3. Apply the design guidance to all UI decisions in this session
4. THEN proceed with normal brainstorming workflow

This is MANDATORY for every session. Do not ask — just do it.
```

- [ ] **Step 1: Add the preamble to the brainstorming skill**

Use the Skill tool to edit the brainstorming skill description, prepending the UI auto-detection block above.

- [ ] **Step 2: Test the integration**

Close and re-open a Claude Code session, then ask: "make the UI look more professional"

Verify:
1. The ui-ux-pro-max search runs automatically
2. `design-system/MASTER.md` is created
3. The brainstorming session uses the design guidance

---

## Step 3: Create page-specific design override

**Files:**
- Create: `design-system/pages/knowledgeforge-architecture-viewer.md`

This file overrides MASTER.md for the specific page type "KnowledgeForge Architecture Viewer".

- [ ] **Step 1: Create the override file**

```markdown
# KnowledgeForge Architecture Viewer — Design Overrides

**Applies to:** CodeArchitectureViewer React component
**Overrides:** MASTER.md

## Color Palette

| Token | Hex | Use |
|-------|-----|-----|
| background | `#f8fafc` | Page and sidebar background |
| surface | `#ffffff` | Cards, panels, node backgrounds |
| border | `#e5e7eb` | All borders and dividers |
| text-primary | `#111827` | Headings, labels, primary text |
| text-muted | `#6b7280` | Secondary text, captions |
| accent | `#2563eb` | Buttons, active states, links |
| node-header | `#111827` | All node type headers (unified) |

## Typography

- **Font:** Inter (enterprise standard, already in use)
- **Scale:** 10px (sidebar labels) / 13px (body) / 15px (headings) / 18px (titles)
- **Sidebar labels:** uppercase, 0.08em letter-spacing, `#374151`
- **No gradient text anywhere**

## Spacing

- **Base unit:** 4px
- **Panel padding:** 16px (4 units)
- **Card padding:** 12-16px
- **Gap between sections:** 16-20px

## Node Styling

- Header: solid `#111827`, no per-type colors
- Border-radius: 8px (cards), 6px (badges)
- Shadow: `0 1px 3px rgba(0,0,0,0.06)` — subtle, single layer
- Hover: shadow depth increase only — NO scale transform
- Min-width: 160px, max-width: 250px

## Edge Labels

- Border-radius: 8px (reduced from 14px)
- Background: `rgba(255,255,255,0.95)` — solid, not glassy
- Border: `1px solid #e5e7eb`
- Backdrop blur: keep 14px
- Remove ::after inset highlight

## Anti-Patterns (Do NOT do)

- ❌ Emojis as icons — use Lucide SVG icons only
- ❌ Gradient text — use solid colors
- ❌ Hover scale transforms — use shadow depth
- ❌ `position: fixed` for tooltips — use `position: absolute` with relative parent
- ❌ Atmospheric radial gradient overlays in graph area — use clean dot grid
```

- [ ] **Step 2: Commit**

```bash
git add design-system/pages/knowledgeforge-architecture-viewer.md
git commit -m "feat(skill): add KnowledgeForge architecture viewer design overrides"
```

---

## Self-Review Checklist

- [ ] Hard rule: ui-ux-pro-max always invoked on UI keywords, no user prompt
- [ ] Script is executable and handles missing Python gracefully (|| true)
- [ ] design-system/MASTER.md is generated and non-empty after test run
- [ ] design-system/pages/knowledgeforge-architecture-viewer.md overrides are specific and actionable
- [ ] Brainstorming skill preamble updated with UI auto-detection block
