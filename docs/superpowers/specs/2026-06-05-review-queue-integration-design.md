# Review Queue — Integrate Into Workspace Tab

**Date:** 2026-06-05
**Status:** Design approved (pending spec review)
**Scope:** UI-only integration. Backend `/api/v1/review/*` endpoints untouched.

---

## Problem

The KnowledgeForge UI exposes the Human-in-the-Loop review queue as a top-level nav tab (`/review` → `ReviewDashboard`). This adds a 5th tab and forces reviewers to switch context away from the Workspace (upload + extraction trigger) to act on low-confidence extraction results.

## Goal

Remove the top-level Review Queue nav tab and embed the review table inline within the Workspace tab, immediately below the file uploader. Reviewers upload + review in one scroll.

## Non-Goals

- Removing or refactoring the backend `/api/v1/review/*` API
- Renaming `ReviewDashboard` component
- Changing the review data model or persistence
- Touching the Recommendation modal's `reviewNotes` field (unrelated internal "review notes" string)

---

## Architecture

**Single-page integration.** The `/workspace` route gains a sub-section below the existing `FileUploader` block. The `/review` route is removed and replaced with a redirect to `/workspace` for backwards-compat (bookmarks, external links, dev history).

```
/workspace
  ├─ Section header: "Build the Risk Evidence Baseline"
  ├─ FileUploader
  ├─ Uploaded files list (existing, conditional)
  ├─ <hr> divider
  └─ <section class="review-section">
       <h2>Pending Review Items</h2>
       <ReviewDashboard />   ← embedded as-is
```

`ReviewDashboard` is rendered as a child of the Workspace route. React state in `ReviewDashboard` (`items`, `total`, `runId`, `overrideField`, `overrideValue`) is local to the dashboard and unaffected by uploader re-renders.

---

## Components

### Module: `App.tsx` (modified)
- **Responsibility:** Routing + nav for the SPA
- **Interface:** Owns `<Routes>` and `<Navigation>`; consumes no props
- **Dependencies:** `react-router-dom`, `lucide-react`, child route components
- **Size target:** ~360 lines after change (current ~370, will drop ~10 lines from review removal, add ~8 for inline embed + redirect)

**Changes:**
1. Remove the `review` entry from `navItems` array
2. Remove `if (path.startsWith("/review")) return "review";` from `getActiveTab()`
3. Remove `<Route path="/review" element={<ReviewDashboard />} />`
4. Add `<Route path="/review/*" element={<Navigate to="/workspace" replace />} />` (wildcard redirect — catches `/review` and any `/review/*` deep links; renders 404-free)
5. In the `/workspace` route element, append after the `uploaded-files` block:
   ```tsx
   <hr className="workspace-divider" />
   <section className="review-section">
     <h2>Pending Review Items</h2>
     <ReviewDashboard />
   </section>
   ```
6. Keep the `ReviewDashboard` import (now used in `/workspace` route element)

### Module: `pages/ReviewDashboard.tsx` (unchanged)
- **Responsibility:** Render pending review items table + approve/reject/override/bulk-approve actions
- **Interface:** Props: none. State: `items`, `total`, `runId`, `loading`, `overrideField`, `overrideValue`
- **Dependencies:** `services/reviewService`, React hooks
- **Size target:** ~275 lines (current, OK)

**No changes.** The component is reused as-is. Its internal `2rem` padding wrapper may visually clash with Workspace padding — visual test required; if clash, move padding to `.review-section` in `App.scss` and zero out the component's outer padding.

### Module: `services/reviewService.ts` (unchanged)
- **Responsibility:** HTTP client for `/api/v1/review/*` endpoints
- **Interface:** `listPending`, `approve`, `reject`, `override`, `bulkApprove`
- **Dependencies:** `services/api`
- **Size target:** ~55 lines (current, OK)

**No changes.**

### Module: `e2e/specs/05-review-queue.spec.ts` (modified)
- **Responsibility:** Playwright coverage for the review queue UI
- **Interface:** `test.describe('Review Queue', ...)` block
- **Dependencies:** `@playwright/test`
- **Size target:** current size, OK

**Changes:**
1. `page.goto('/review')` → `page.goto('/workspace')`
2. Selector for h1 "Review Queue" → selector for h2 "Pending Review Items"
3. All other selectors (`Bulk Approve`, table, action buttons) remain — they target elements that still exist on the page

---

## Data Flow (unchanged)

1. User uploads repo via `FileUploader` → backend creates extraction run
2. Backend `dependency_detector.py` emits `ReviewItem` rows for low-confidence dependencies
3. `ReviewDashboard` mounts inside Workspace → `loadPending()` → `GET /api/v1/review/pending?run_id=latest`
4. User clicks Approve/Reject/Override → `reviewService` POSTs → `loadPending()` refreshes
5. Default `runId="latest"` resolves to most recent run (existing backend behavior)

---

## Visual Treatment

- **Divider:** inline `<hr>` with default browser styling OR one-line SCSS rule:
  ```scss
  .workspace-divider { margin: 2rem 0; border: 0; border-top: 1px solid #e5e7eb; }
  ```
  Decision deferred to implementation: use inline `style={{ margin: "2rem 0", border: 0, borderTop: "1px solid #e5e7eb" }}` if no other `<hr>` rules exist in `App.scss`; otherwise add SCSS rule.
- **Section heading:** `<h2>Pending Review Items</h2>` matches existing `section-header h1` style scale.
- **Empty state:** existing "No pending items. All clear!" message displays in section, no special styling needed.
- **Padding clash:** if `ReviewDashboard`'s `padding: 2rem` outer wrapper looks wrong inside workspace, strip it in the embedded copy and let the section inherit workspace padding. (If stripping, the simpler option is a small CSS override rather than a component refactor.)

---

## Edge Cases

1. **No pending items on first load:** Workspace shows uploader + "No pending items. All clear!" — same as old ReviewQueue at empty state. ✓
2. **Legacy `/review` and `/review/*` URLs:** wildcard-redirect to `/workspace` via `<Navigate replace>`. No 404 for any sub-path. ✓
3. **ReviewDashboard re-renders when uploader re-renders:** React sibling components have independent state. `ReviewDashboard` state survives. ✓
4. **`runId="latest"` default:** unchanged, resolves via backend. ✓
5. **Mobile / narrow viewport:** table overflows; existing `ReviewDashboard` does not handle this. Out of scope — same behavior as before, no regression. (Acceptable: review workflow is desktop-first per team norm.)
6. **External scripts or curl hitting `/api/v1/review/*`:** unchanged. Backend endpoints stay. ✓
7. **Recommendation modal's internal `reviewNotes` string:** unrelated to this change. Out of scope. ✓

---

## Testing

- **E2E:** Update `05-review-queue.spec.ts` to navigate to `/workspace` and assert the "Pending Review Items" section is visible. Re-run Playwright suite.
- **Unit:** No unit test changes (no new component logic).
- **Manual smoke:** Open `/workspace`, upload a repo (or use existing seeded data), confirm review table loads below uploader, perform one Approve, confirm row disappears.
- **Regression:** Visit `/review` in browser → confirm redirect to `/workspace` (no 404).

---

## Files Touched

| File | Action | Lines (net) |
|------|--------|-------------|
| `sources/UI/src/App.tsx` | modify | -7, +8 |
| `sources/UI/e2e/specs/05-review-queue.spec.ts` | modify | -2, +2 |
| `sources/UI/src/App.scss` | optional modify | +0–2 |
| `sources/UI/src/pages/ReviewDashboard.tsx` | unchanged | 0 |
| `sources/UI/src/services/reviewService.ts` | unchanged | 0 |
| Backend (`review.py`, models, tests) | unchanged | 0 |

---

## Open Questions

None — all grill-me questions resolved with recommended options.
