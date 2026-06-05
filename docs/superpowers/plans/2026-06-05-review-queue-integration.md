# Review Queue Workspace Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the Human-in-the-Loop review queue as a sub-section of the Workspace tab, removing the standalone `/review` nav route. Reviewers upload + review in one scroll.

**Architecture:** UI-only refactor. The `/workspace` route renders `<FileUploader />` followed by an inline `<ReviewDashboard />` inside a new `<section className="review-section">`. The `/review` route is removed and replaced with a wildcard `<Navigate>` redirect to `/workspace` for backwards compat. Backend `/api/v1/review/*` endpoints and `ReviewDashboard`/`reviewService` are untouched.

**Tech Stack:** React 18, react-router-dom v6, TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-05-review-queue-integration-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `sources/UI/src/App.tsx` | modify | Routing + nav. Removes `review` navItem, `/review` Route, `getActiveTab` branch. Adds wildcard `/review/*` redirect. Embeds `<ReviewDashboard />` inside `/workspace` route. |
| `sources/UI/e2e/specs/05-review-queue.spec.ts` | modify | Playwright coverage. Swaps `goto('/review')` → `goto('/workspace')` and h1 selector → h2 selector for the section heading. |
| `sources/UI/src/App.scss` | conditional modify | Add `.workspace-divider` rule ONLY if inline `<hr>` styling clashes. Defer to Task 4 smoke check. |
| `sources/UI/src/pages/ReviewDashboard.tsx` | unchanged | Reused as-is. |
| `sources/UI/src/services/reviewService.ts` | unchanged | Reused as-is. |
| `sources/Api/app/endpoint/v1/routes/review.py` | unchanged | Backend untouched. |

---

## Task 1: Create branch + verify baseline

**Files:** none

- [ ] **Step 1: Create and checkout feature branch**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git checkout main
git pull origin main
git checkout -b relentless/review-queue-integration
```

- [ ] **Step 2: Verify backend is running for e2e**

```bash
docker compose ps api
```

Expected: `api` service listed as `running` (or `Up`). If not, start it:

```bash
docker compose up -d api
```

- [ ] **Step 3: Run baseline e2e suite (sanity)**

```bash
cd sources/UI
npm run test:e2e -- 05-review-queue.spec.ts
```

Expected: 7 tests pass (current `/review` route still works pre-change).

- [ ] **Step 4: Commit branch marker (skip if no changes)**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git status  # should show clean
```

No commit needed if clean. Branch created.

---

## Task 2: Update e2e spec to new URL and selector (failing test)

**Files:**
- Modify: `sources/UI/e2e/specs/05-review-queue.spec.ts:3-10`

- [ ] **Step 1: Change `page.goto` URL**

Replace line 5:
```ts
    await page.goto('/review');
```
with:
```ts
    await page.goto('/workspace');
```

- [ ] **Step 2: Change h1 heading assertion to h2**

Replace line 9-10:
```ts
  test('page loads with Review Queue heading', async ({ page }) => {
    await expect(page.locator('h1').filter({ hasText: 'Review Queue' })).toBeVisible({ timeout: 10000 });
  });
```
with:
```ts
  test('section loads with Pending Review Items heading', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Pending Review Items' })).toBeVisible({ timeout: 10000 });
  });
```

- [ ] **Step 3: Run e2e spec to verify it fails**

```bash
cd sources/UI
npm run test:e2e -- 05-review-queue.spec.ts
```

Expected: FAIL with timeout on h2 locator (heading not yet present in DOM). Other tests in the file should also fail (e.g., "Bulk Approve" button may not be visible if the embed is not yet in place). This is the RED phase.

- [ ] **Step 4: Commit failing test**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git add sources/UI/e2e/specs/05-review-queue.spec.ts
git commit -m "test(e2e): update review queue spec to /workspace + h2 selector"
```

---

## Task 3: Modify App.tsx — remove nav item, route, add redirect, embed ReviewDashboard

**Files:**
- Modify: `sources/UI/src/App.tsx`

- [ ] **Step 1: Remove `review` navItem entry**

In `App.tsx`, remove the entire `review` object from the `navItems` array (lines 92-97 in current file):

```tsx
    {
      id: "review",
      label: "Review Queue",
      icon: <Activity size={20} />,
      path: "/review",
    },
```

After removal, `navItems` contains 4 entries: workspace, code-architecture, metrics, settings.

- [ ] **Step 2: Remove `getActiveTab` branch for `/review`**

In `App.tsx`, remove the line in `getActiveTab()` (line 203):

```tsx
    if (path.startsWith("/review")) return "review";
```

After removal, `getActiveTab` returns "code-architecture" as the default for any unmatched path.

- [ ] **Step 3: Replace `/review` Route with wildcard redirect**

In `App.tsx`, replace the existing Route line (line 352):

```tsx
            <Route path="/review" element={<ReviewDashboard />} />
```
with:
```tsx
            <Route path="/review/*" element={<Navigate to="/workspace" replace />} />
```

This catches `/review` and any `/review/*` sub-path and redirects to `/workspace`.

- [ ] **Step 4: Embed `<ReviewDashboard />` inside `/workspace` route**

In `App.tsx`, inside the `/workspace` route element, find the closing of the `uploaded-files` conditional block (line ~308 area, the closing `</div>` of the `uploaded-files` div, before the closing `</div>` of the outer `upload-section` wrapper at line ~309). Add the embed after the `uploaded-files` closing `</div>` and before the outer `</div>`:

```tsx
                  {files.length > 0 && (
                    <div className="uploaded-files">
                      <h3>Uploaded Files ({files.length})</h3>
                      <ul>
                        {files.map((file, index) => (
                          <li key={index}>
                            <strong>{file.name}</strong>
                            <br />
                            <small>
                              {file.headers.length} columns, {file.rowCount}{" "}
                              rows
                            </small>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <hr
                    style={{
                      margin: "2rem 0",
                      border: 0,
                      borderTop: "1px solid #e5e7eb",
                    }}
                  />
                  <section className="review-section">
                    <h2>Pending Review Items</h2>
                    <ReviewDashboard />
                  </section>
                </div>
              }
            />
```

The `import { ReviewDashboard }` line at the top of `App.tsx` (line 26) is kept — it is now used in the embed.

- [ ] **Step 5: Run e2e spec to verify it passes (GREEN)**

```bash
cd sources/UI
npm run test:e2e -- 05-review-queue.spec.ts
```

Expected: All 7 tests pass. The h2 "Pending Review Items" locator finds the heading, Bulk Approve button is visible, and the table/empty state renders below the uploader.

- [ ] **Step 6: Commit App.tsx changes**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git add sources/UI/src/App.tsx
git commit -m "feat(ui): embed review queue in workspace tab, add /review/* redirect"
```

---

## Task 4: Visual smoke check + conditional SCSS

**Files:**
- Modify (conditional): `sources/UI/src/App.scss`

- [ ] **Step 1: Run dev server, manually inspect /workspace**

```bash
cd sources/UI
npm run dev
```

Open `http://localhost:3010/workspace` in a browser. Verify:
- Page header "Build the Risk Evidence Baseline" renders
- FileUploader renders below header
- `<hr>` divider is visible
- "Pending Review Items" h2 renders below divider
- ReviewDashboard table (or empty state "No pending items") renders below h2

- [ ] **Step 2: Verify /review redirect**

Open `http://localhost:3010/review` in a browser. Verify: URL changes to `/workspace`, workspace content renders. No 404.

- [ ] **Step 3: Verify padding/margin visual**

Check whether `ReviewDashboard`'s outer `<div style={{ padding: "2rem" }}>` causes excessive whitespace inside the workspace. If yes, proceed to Step 4. If no, skip to Step 5.

- [ ] **Step 4 (conditional): Add `.review-section` override in App.scss**

ONLY execute this step if Step 3 found a visual clash.

Open `sources/UI/src/App.scss`. Append at the end of the file:

```scss
.review-section {
  margin-top: 0;
  // Reset ReviewDashboard's outer padding to inherit workspace padding
  > div:first-child {
    padding: 0 !important;
  }
}
```

Run `npm run dev` again and re-verify the layout. If still clashing, iterate (e.g., add `padding: 1.5rem 0`).

- [ ] **Step 5: If SCSS was modified, commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git add sources/UI/src/App.scss
git commit -m "style(ui): reset ReviewDashboard padding in workspace embed"
```

If SCSS was not modified, skip this step.

- [ ] **Step 6: Stop dev server**

```bash
pkill -f "vite" || true
```

(Ctrl-C in dev terminal also works.)

---

## Task 5: Run full frontend test suite

**Files:** none

- [ ] **Step 1: Run Vitest unit tests**

```bash
cd sources/UI
npm run test
```

Expected: All unit tests pass. Existing `ReviewDashboard` tests should pass unchanged since the component is reused as-is.

- [ ] **Step 2: Run full e2e suite (not just review spec)**

```bash
cd sources/UI
npm run test:e2e
```

Expected: All e2e tests pass, including `04-llm-enrichment.spec.ts` (which uses unrelated "review status" string for LLM enrichment data) and `05-review-queue.spec.ts` (now pointing at /workspace).

- [ ] **Step 3: If any test fails, investigate and fix**

Common failure modes:
- **04-llm-enrichment test fails:** This is an unrelated test that uses the word "review" for LLM enrichment data. Should not be affected. If it is, check that the CodeArchitectureViewer still renders the `review_status` detail row.
- **05-review-queue Bulk Approve test fails:** Verify the embed is rendering ReviewDashboard (inspect DOM via Playwright trace).
- **Other e2e test fails with navigation error:** Check that `/review` URL change in this PR didn't break a test that explicitly navigates there.

If failures are real regressions, fix and re-run. Document any fixes in the commit.

---

## Task 6: Run check-all (type-check + lint + format)

**Files:** none (auto-fix may modify files)

- [ ] **Step 1: Run check-all**

```bash
cd sources/UI
npm run check-all
```

Expected: Pass with no errors. If prettier format errors appear, run `npm run fix-all` and re-run check-all.

- [ ] **Step 2: If fix-all modified files, commit**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git status
```

If formatted/linted files appear, commit:
```bash
git add sources/UI/
git commit -m "style(ui): apply prettier + eslint fixes"
```

If no changes, skip this step.

---

## Task 7: Final verification + manual smoke summary

**Files:** none

- [ ] **Step 1: Verify branch state**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
git log --oneline main..HEAD
git diff main --stat
```

Expected: 3-5 commits ahead of main, ~3 files changed, ~10 lines net.

- [ ] **Step 2: Final manual smoke (recap)**

1. `docker compose up -d api` (if not running)
2. `cd sources/UI && npm run dev`
3. Visit `http://localhost:3010/workspace`:
   - Nav has 4 items (no "Review Queue")
   - FileUploader + Pending Review Items section both render
4. Visit `http://localhost:3010/review`:
   - URL redirects to `/workspace`
   - No 404 in console
5. Approve a test review item (if data exists) → confirm row disappears and count updates
6. Stop dev server

- [ ] **Step 3: Hand off to PR creation**

Plan is complete. The branch `relentless/review-queue-integration` is ready for:
- `git push origin relentless/review-queue-integration`
- Open PR against `main`
- (Optional) Squash-merge via Vercel/GitHub

---

## Self-Review Checklist (run by plan author)

- [x] **Spec coverage:**
  - Spec: "Remove the `review` navItem" → Task 3 Step 1
  - Spec: "Remove `/review` Route" → Task 3 Step 3
  - Spec: "Add `<Navigate>` redirect" → Task 3 Step 3
  - Spec: "Embed `<ReviewDashboard />` in /workspace" → Task 3 Step 4
  - Spec: "Update e2e spec" → Task 2 Steps 1-2
  - Spec: "Optional SCSS" → Task 4 Steps 3-5
  - Spec: "Manual smoke" → Task 7 Step 2
  - Spec: "E2E test run" → Task 5 Step 2
  - Spec: "Regression: /review redirect" → Task 7 Step 2
  - Spec: "Padding clash" → Task 4 Steps 3-4

- [x] **Placeholder scan:** No TBD/TODO. All steps have concrete code or commands.

- [x] **Type consistency:** `ReviewDashboard` referenced consistently as imported React component. No signature changes. `navItems` array referenced consistently as `NavItem[]` type.

- [x] **No-go compliance:** No file deletions of user-authored files. No pushes to main. No `.env` modifications. No paid API calls.
