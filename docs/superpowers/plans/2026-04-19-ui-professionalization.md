# UI Professionalization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing React frontend to an Enterprise Dashboard aesthetic — muted palette, structured hierarchy, tighter spacing, stronger contrast — while keeping the 2-panel (graph + chat) layout and component structure.

**Architecture:** CSS token refactor in SCSS files + targeted TSX component tweaks. No layout restructuring.

**Tech Stack:** React 18, TypeScript, Sass, ReactFlow

---

## File Map

```
sources/UI/src/@components/architecture-map/CodeArchitectureViewer/
  CodeArchitectureViewer.scss    # MODIFY — color tokens, typography, node/edge styles
  components/
    NodeDetailsPanel.tsx          # MODIFY — chat panel bubble styles, header
    MetricsBar.tsx                 # MODIFY — button/pill styles, layout
    FiltersSidebar.tsx            # MODIFY — section header typography
    CustomNode.tsx                # MODIFY — node card shadow, header color
    C4Edge.tsx                   # MODIFY — edge label styling
```

**Working directory for UI commands:** `sources/UI/`

---

## Color & Token Reference

All old → new color mappings:

| Token | Old Value | New Value |
|-------|-----------|-----------|
| Background | `#f8fbff` + gradient | `#f8fafc` |
| Graph bg | `#fdfefe` + gradient | `#fafafa` + dot grid |
| Border primary | `#dbe5f0` | `#e5e7eb` |
| Text primary | `#1a1a1a` | `#111827` |
| Text muted | `#9e9e9e` | `#6b7280` |
| Node header | per-type colors | `#111827` (all) |
| Accent | `#6366f1` | `#2563eb` |
| Surface | `#ffffff` | `#ffffff` |
| Sidebar bg | `#f8f9fa` | `#f9fafb` |

---

### Task 1: Refactor CodeArchitectureViewer.scss — color tokens

**Files:**
- Modify: `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss`

**This is the main styling file (~2400 lines). The refactor targets the CSS custom properties and base tokens.**

- [ ] **Step 1: Audit current color usage**

```bash
grep -n "#[0-9a-fA-F]\{6\}" sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss | grep -v "fff\|000" | head -40
```

Note which colors appear where. Then apply the token changes.

- [ ] **Step 2: Replace color tokens**

Apply the following global replacements (using the Edit tool with replace_all):

1. Replace `#dbe5f0` with `#e5e7eb` (border color)
2. Replace `#1a1a1a` with `#111827` (text primary)
3. Replace `#9e9e9e` with `#6b7280` (text muted)
4. Replace `#6366f1` with `#2563eb` (accent — only where it's the primary accent, not decorative gradients)
5. Replace `#f8fbff` with `#f8fafc` (background)
6. Replace `#fdfefe` with `#fafafa` (graph background)

- [ ] **Step 3: Remove gradient overlays from graph container**

Find and remove:
```scss
// DELETE these from .graph-container
&::before {
  content: '';
  position: absolute;
  inset: -12% -8%;
  background:
    radial-gradient(circle at 18% 12%, rgba(37, 99, 235, 0.1), transparent 24%),
    radial-gradient(circle at 88% 10%, rgba(56, 189, 248, 0.1), transparent 22%),
    radial-gradient(circle at 56% 92%, rgba(99, 102, 241, 0.08), transparent 26%);
  pointer-events: none;
}
```

Replace with clean dot grid:
```scss
background-image: radial-gradient(circle, #e1e4e8 1px, transparent 1px);
background-size: 24px 24px;
```

- [ ] **Step 4: Simplify node styling — remove per-type colors, use unified header**

Find the `.node-type-*` classes and replace all of them (lines ~112-156) with:

```scss
// Enterprise: single header color for all container types
.node-type-container,
.node-type-class,
.node-type-function,
.node-type-method,
.node-type-module,
.node-type-file,
.node-type-component {
  .node-header {
    background: #111827;
    box-shadow: 0 2px 4px rgba(17, 24, 39, 0.15);
  }
}
```

- [ ] **Step 5: Update node hover — remove scale transform, use shadow only**

Find `&:hover` in `.react-flow__node-custom` and replace scale with shadow depth:

```scss
// REPLACE this:
&:hover {
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.1),
    0 8px 24px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px) scale(1.02);  // REMOVE scale
}

// WITH this:
&:hover {
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.12),
    0 8px 24px rgba(0, 0, 0, 0.08);
}
```

- [ ] **Step 6: Simplify edge label styling**

Find `.c4-edge-label-inner` and replace:
```scss
// REPLACE background with solid:
background: rgba(255, 255, 255, 0.95);  // was: rgba(255, 255, 255, 0.94)
// REMOVE the ::after inset highlight
&::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  pointer-events: none;
}  // DELETE THIS BLOCK
// REPLACE border-radius: 14px with 8px
border-radius: 8px;  // was 14px
```

- [ ] **Step 7: Remove decorative gradients from description rows**

Find `.description-row` and remove:
```scss
// REMOVE this:
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
box-shadow: 0 8px 16px rgba(102, 126, 234, 0.2);

// REPLACE with:
background: #f8fafc;
border: 1px solid #e5e7eb;
```

- [ ] **Step 8: Run format and lint**

```bash
cd sources/UI && npm run fix-all
```

Expected: Clean pass (no errors)

- [ ] **Step 9: Commit**

```bash
git add src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss
git commit -m "refactor(ui): enterprise color tokens and typography"
```

---

### Task 2: Fix MetricsBar accessibility and styles

**Files:**
- Modify: `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/MetricsBar.tsx`
- Modify: `CodeArchitectureViewer.scss` (already covered in Task 1)

- [ ] **Step 1: Read the MetricsBar component**

```bash
head -80 sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/MetricsBar.tsx
```

- [ ] **Step 2: Add cursor-pointer to all interactive elements**

In the JSX, add `className="cursor-pointer"` to buttons and clickable divs that don't already have it.

- [ ] **Step 3: Add visible focus rings**

Add to the Extract button's className:
```tsx
className="extract-btn cursor-pointer"
```
And ensure the CSS has:
```scss
.extract-btn:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
```

- [ ] **Step 4: Run tests**

```bash
cd sources/UI && npm run test -- --run src/@components/architecture-map/CodeArchitectureViewer/components/MetricsBar.test.tsx
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/@components/architecture-map/CodeArchitectureViewer/components/MetricsBar.tsx
git commit -m "fix(ui): MetricsBar accessibility — cursor-pointer and focus rings"
```

---

### Task 3: Fix tooltip positioning (z-index stacking context)

**Files:**
- Modify: `CodeArchitectureViewer.scss`

**The issue:** Tooltips use `position: fixed` which causes z-index stacking context problems. Fix by using `position: absolute` on the tooltip wrapper with `position: relative` parent.

- [ ] **Step 1: Find tooltip CSS**

```bash
grep -n "position: fixed" sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss
```

- [ ] **Step 2: Replace all `position: fixed` tooltips with `position: absolute`**

For each tooltip rule, add `position: relative` to the parent element and change tooltip to `position: absolute`. Example transformation:

```scss
// BEFORE (broken):
.pill:hover::after {
  position: fixed;
  top: auto;
  bottom: 15vh;
  left: 50%;
  transform: translateX(-50%);
  /* ... */
}

// AFTER (fixed):
.pill {
  position: relative;
}
.pill:hover::after {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  /* ... */
}
```

Apply this pattern to all tooltip usages (`.pill:hover::after`, `.tooltip-hint:hover .tooltip-content`, `.detail-row .tooltip-content`).

- [ ] **Step 3: Verify no `position: fixed` remains for tooltips**

```bash
grep -n "position: fixed" sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss
```
Should return 0 results for tooltip-related CSS (only legitimate uses like modal dialogs should remain).

- [ ] **Step 4: Run fix-all and tests**

```bash
cd sources/UI && npm run fix-all && npm run test -- --run
```

- [ ] **Step 5: Commit**

```bash
git add src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss
git commit -m "fix(ui): tooltip position fixed->absolute to fix z-index stacking"
```

---

### Task 4: Update NodeDetailsPanel chat header and message bubbles

**Files:**
- Modify: `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.tsx`

- [ ] **Step 1: Read the panel header JSX**

Find the `.chat-header` section in the TSX and the `.chat-messages .message-content` CSS class.

- [ ] **Step 2: Update message bubble background**

In SCSS, find `.chat-message .message-content` and update:
```scss
.message-content {
  background: #f3f4f6;      // was: varied gradients
  border: 1px solid #e5e7eb;  // was: #e2e8f0
  border-radius: 12px;
}
```

- [ ] **Step 3: Simplify the chat input**

In the `.chat-input-wrapper`:
```scss
.chat-input-wrapper {
  background: #f9fafb;   // was: #f8fafc
  border: 1px solid #e5e7eb;  // was: #dbe4f0
  border-radius: 14px;
}
```

- [ ] **Step 4: Run fix-all and test**

```bash
cd sources/UI && npm run fix-all && npm run test -- --run src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.tsx
git commit -m "refactor(ui): NodeDetailsPanel chat bubbles to enterprise style"
```

---

### Task 5: Verify all UI tests pass

**Files:**
- Test: All modified TSX/SCSS files

- [ ] **Step 1: Run the full UI test suite**

```bash
cd sources/UI && npm run test -- --run
```

Expected: All 84 tests pass

- [ ] **Step 2: Run type-check and lint**

```bash
cd sources/UI && npm run check-all
```

Expected: Clean pass

- [ ] **Step 3: Commit all remaining changes**

```bash
git add src/@components/architecture-map/CodeArchitectureViewer/
git commit -m "refactor(ui): enterprise dashboard SCSS and component polish"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All items in 4C-2 through 4C-4 addressed
- [ ] No layout restructure — 2-panel layout unchanged
- [ ] Color tokens consistent across all modified files
- [ ] Accessibility: tooltip fixed, focus rings added, cursor-pointer on interactives
- [ ] All tests pass: `npm run test -- --run`
- [ ] All checks pass: `npm run check-all`
