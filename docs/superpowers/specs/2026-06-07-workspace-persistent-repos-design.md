# Workspace — Persistent Repository Queue

**Date:** 2026-06-07
**Status:** Design approved (pending spec review)
**Scope:** UI-only. No backend changes.

---

## Problem

`FileUploader` (mounted only on `/workspace` route) owns the `repos: RepoEntry[]` state and the polling intervals. When the user navigates to another tab (`/code-architecture`, `/metrics`, `/settings`), React Router unmounts `FileUploader` → repos list disappears → poll intervals cleared → in-flight extraction progress is lost on the client (backend continues, but the user has no visible state). Returning to `/workspace` shows an empty queue, forcing the user to re-add every URL.

Additionally, the existing `FileUploader` mixes two concerns in one 678-line component: input form (URL/token/folder) and queue display (repo list, progress bars, extract-all/clear actions). Splitting these clarifies ownership and makes the persistent queue usable as a "file explorer" of the user's uploaded repos.

## Goal

- Repos and their status survive any tab switch in the SPA.
- Add new `RepoExplorer` component — persistent, dedicated view of the repo queue.
- `FileUploader` becomes a thin input panel; queue state lives in a new `RepoProvider` Context above the Router.
- Multi-repo support: user can queue N repos (GitHub URL or local folder), each with its own status, polling independently.
- Persistence scope: tab-switch only (lost on full page reload, by design — no localStorage).

## Non-Goals

- Page-reload persistence (no localStorage/IndexedDB; out of scope)
- Backend changes (extraction API, task model, WS protocol unchanged)
- File-tree drill-down per repo (would need new backend endpoint to list files in a task)
- Concurrent backend extractions (backend still processes one task at a time per user; UI does not change this)
- Renaming `FileUploader` or any existing service

---

## Architecture

```
App (Router)
└─ <RepoProvider>                  ← new context, lives above Router
   └─ <MainContent>
      ├─ <Navigation>              (unchanged)
      └─ <Routes>
         └─ /workspace
            ├─ <FileUploader />    ← input panel only (read/write via useRepos)
            ├─ <RepoExplorer />    ← new: persistent repo list + actions
            ├─ <hr />
            └─ <ReviewDashboard /> (unchanged)
```

`<RepoProvider>` sits above `<Router>` so its state survives every route change in the app. The provider owns:
- `repos: RepoEntry[]` state
- `pollIntervalsRef: Map<string, interval>` (ref, not state, to avoid re-renders)
- One `wsService.on("message", ...)` subscription (lives for the SPA lifetime)
- `addRepo`, `removeRepo`, `clearAll`, `startExtraction` actions

`FileUploader` and `RepoExplorer` both consume state via the `useRepos()` hook. Neither owns the state. The provider is the only place where polling, WS dispatch, and state mutation live.

---

## Components

### Module: `RepoProvider` (new)
- **Responsibility:** Own repos queue state + WS subscription + per-task polling. Survives tab switches.
- **Interface:** `<RepoProvider>` wrapper component; `useRepos()` hook returns `{ repos, isExtracting, addRepo, removeRepo, clearAll, startExtraction }`
- **Dependencies:** `services/api` (`codeArchitectureAPI`, `wsService`)
- **Size target:** ~200 lines

**Implementation outline:**
```tsx
const RepoContext = createContext<RepoContextValue | null>(null);

export const RepoProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [repos, setRepos] = useState<RepoEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const pollIntervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // One WS subscription, lives for SPA lifetime
  useEffect(() => {
    wsService.connect();
    const handler = (data: unknown) => {
      const msg = data as { task_id?: string; status?: string; message?: string; progress?: number };
      if (!msg?.task_id) return;
      setRepos(prev => prev.map(r => r.taskId === msg.task_id
        ? { ...r, status: msg.status as RepoStatus ?? r.status, message: msg.message ?? r.message, progress: msg.progress ?? r.progress }
        : r));
    };
    wsService.on("message", handler);
    return () => {
      wsService.off("message", handler);
      Object.values(pollIntervalsRef.current).forEach(clearInterval);
    };
  }, []);

  const addRepo = (url: string, token?: string) => { /* validate, dedupe, append */ };
  const removeRepo = (url: string) => { /* filter out */ };
  const clearAll = () => { /* cancel all polls, clear repos */ };
  const startExtraction = async (url: string, append: boolean) => { /* call API, start poll, update status */ };

  return <RepoContext.Provider value={{ repos, isExtracting, addRepo, removeRepo, clearAll, startExtraction }}>{children}</RepoContext.Provider>;
};

export const useRepos = () => {
  const ctx = useContext(RepoContext);
  if (!ctx) throw new Error("useRepos must be used within <RepoProvider>");
  return ctx;
};
```

### Module: `FileUploader` (refactored)
- **Responsibility:** Input panel — GitHub URL form, Local Folder drop zone, GitHub/Local tab switch. Delegates persistence to `RepoProvider`.
- **Interface:** Props: `onExtractionStarted(taskId, file)` (preserved for parent task tracking in `App.tsx`), `showNotification(msg, type)`. Reads/writes via `useRepos()`.
- **Dependencies:** `useRepos()`, `FolderDropZone`, `lucide-react`
- **Size target:** ~180 lines (was 678). Single responsibility: input only.

**Drops:** `repos` state, `wsService.connect/on/off`, `pollStatus`, `uploadZip`, `extractRepo`, `extractAll`, `clearAll`, the `repo-list` JSX block, the `empty-state` block (moved to Explorer), the `repo-actions` block (moved to Explorer).

**Keeps:** URL input + token input, GitHub/Local tab buttons, `FolderDropZone` integration, `addRepo` delegation via `useRepos().addRepo(...)`.

### Module: `RepoExplorer` (new)
- **Responsibility:** Persistent read-only list of repos in `/workspace` with status, progress, and delegated actions. Survives tab switches via context.
- **Interface:** Reads state from `useRepos()`; calls back to `onExtractionStarted(taskId, file)` for parent task tracking.
- **Dependencies:** `useRepos()`, `lucide-react` icons
- **Size target:** ~180 lines. Single responsibility: list display + actions.

**Renders:**
- Empty state (when `repos.length === 0`): "Add one or more repository URLs above" with icon
- Repo items: each shows icon (Folder/Github), URL, status badge (color + label from `statusConfig`), progress bar (when pending/scanning/zipping/uploading), container/component counts (when completed), Re-extract button (when completed), Remove button (when idle/failed)
- Actions footer: Append toggle, Extract All button (with idle count), Clear All button

### Module: `App.tsx` (modified)
- **Responsibility:** Routing + nav for the SPA
- **Interface:** Owns `<Routes>` and `<Navigation>`
- **Dependencies:** `react-router-dom`, `RepoProvider`, child route components
- **Size target:** ~370 lines (current 374, will gain 2 from Provider wrap, lose 8 from dead state cleanup, net -6)

**Changes:**
1. Import `RepoProvider` and `useRepos`
2. Wrap `<Router>` content with `<RepoProvider>` (at the very top, before `<MainContent>`)
3. In `/workspace` route element, render `<FileUploader />` followed by `<RepoExplorer />` (instead of the current FileUploader-only block)
4. Drop dead `files`, `setFiles`, `handleFilesUploaded` state in `MainContent` (unused since FileUploader owns its data)

### Module: `pages/ReviewDashboard.tsx` (unchanged)
- **Responsibility:** Render pending review items table + approve/reject/override/bulk-approve actions
- **Interface:** Props: none. State: local
- **Size target:** ~275 lines (current, OK)

**No changes.**

### Module: `services/api.ts` (unchanged)
- **Responsibility:** HTTP client + WS service
- **Interface:** `codeArchitectureAPI.extractFromGitHub`, `getExtractionStatus`, etc.; `wsService.connect/disconnect/on/off`
- **Size target:** ~430 lines (current, OK)

**No changes.**

---

## Data Flow

**Add a repo:**
```
User pastes URL + clicks Add
  → FileUploader calls useRepos().addRepo(url, token)
    → Provider validates URL, dedupes, appends to repos state with status="idle"
      → RepoExplorer re-renders, shows new repo
```

**Start extraction:**
```
User clicks Extract All in RepoExplorer
  → Explorer calls useRepos().startExtraction(url, append) for each idle/failed repo
    → Provider updates repo status="pending", message="Queuing extraction..."
    → Provider calls codeArchitectureAPI.extractFromGitHub(url, true, append, token)
    → On success: Provider stores taskId, sets status="pending"/"Extraction queued", starts pollStatus(taskId) at 2s interval
    → Provider calls onExtractionStarted(taskId, file) callback → App.tsx sets activeTaskId
    → Backend runs extraction, emits WS messages
    → WS message arrives → Provider's handler updates matching repo by taskId
    → pollStatus also runs as backup, updates status from REST
    → On completed/failed: poll interval cleared
```

**Tab switch:**
```
User clicks "Code Architecture" tab
  → React Router unmounts /workspace route element
    → FileUploader and RepoExplorer unmount (their useEffects clean up)
    → Provider stays mounted (above Router)
    → pollIntervalsRef entries still active
  → User clicks "Workspace" tab
    → /workspace route element remounts
    → FileUploader + RepoExplorer mount, call useRepos()
    → Provider returns current repos state — all entries still present
    → In-flight extractions continue (WS still active, polls still running)
```

**Remove a repo:**
```
User clicks X on a repo item in RepoExplorer
  → Explorer calls useRepos().removeRepo(url)
    → Provider filters out, updates state
      → RepoExplorer re-renders without that repo
    → If repo had an active poll: clearInterval + delete from pollIntervalsRef
```

---

## Visual Treatment

- **Layout:** `<FileUploader>` (input form) on top, `<RepoExplorer>` (queue list) below, both inside the existing `.upload-section` div. No new layout primitives.
- **Styling:** Reuse the existing `.repo-list`, `.repo-item`, `.repo-item__*`, `.empty-state`, `.repo-actions` SCSS classes from `FileUploader.scss`. Move the relevant rules to a new `RepoExplorer.scss` (or co-locate in `FileUploader.scss` and import from both). Keep visual identity identical to current `repo-list` block — no design changes, only relocation.
- **Empty state** lives in `RepoExplorer`, shows when `repos.length === 0`. "Add one or more repository URLs above" hint.
- **Status badge colors / icons** preserved (idle, pending, scanning, completed, failed, zipping, uploading).

---

## Edge Cases

1. **Tab switch during in-flight extraction:** provider stays mounted, polls continue, WS still updates. Returning to `/workspace` shows the latest status. ✓
2. **WS message arrives for a removed repo:** provider filters by `taskId`, no match → no state update. ✓
3. **Network failure during `extractFromGitHub` call:** provider sets repo `status="failed"`, calls `showNotification` with error message. ✓
4. **Polling network errors:** 10-consecutive-error threshold preserved from current code (~20s of no response stops the poll). Repo remains in last-known status. ✓
5. **`clearAll` while extractions are in progress:** cancel all poll intervals first, then clear state. In-flight backend tasks continue server-side; client loses visibility. Acceptable — user explicitly chose to clear. (Optional: show notification "Cleared queue; N background tasks still running on server".)
6. **Add same URL twice (race):** dedupe check happens in `addRepo` before state mutation. Second add is rejected with input error. ✓
7. **Empty URL / invalid URL:** validation in `addRepo` shows error. ✓
8. **Many repos in queue (e.g., 20+):** RepoExplorer renders all items in a vertical list with scroll. No virtualization needed at this scale. If it becomes a problem, virtualize later. (YAGNI.)
9. **User uploads repo from Local Folder, then switches tab mid-upload:** upload XHR (in `FolderDropZone`) continues; poll starts on taskId return; provider picks up via WS. ✓
10. **Provider rendered outside `<Router>`:** ensure no `useLocation` or router-specific hooks are used inside `RepoProvider`. Currently no such hooks are needed. ✓
11. **HMR / dev-mode remount of provider:** state resets to `[]` on hot-reload. Acceptable — dev only, doesn't affect production builds. ✓

---

## Testing

- **Unit: `RepoProvider.test.tsx`** — render with `renderHook` from `@testing-library/react`:
  - `addRepo` with valid URL appends to `repos`
  - `addRepo` with duplicate URL returns error
  - `addRepo` with invalid URL returns error
  - `removeRepo` filters out by URL
  - `clearAll` empties repos and cancels polls
  - `startExtraction` calls API, sets status="pending", registers taskId
  - `updateFromWS` updates matching repo
  - WS message for unknown taskId is a no-op
- **Unit: `useRepos.test.tsx`** — throws if used outside provider; returns context value inside provider.
- **Unit: `FileUploader.test.tsx` (refactored)** — URL input + Add button calls `useRepos().addRepo`; GitHub/Local tab switching still works; `FolderDropZone` integration preserved.
- **Unit: `RepoExplorer.test.tsx` (new)** — renders empty state when no repos; renders repo items with status badges; Remove/Extract All/Append toggle trigger correct context actions.
- **E2E: `01-workspace.spec.ts` (extend existing or new spec)** —
  - Upload repo A → switch to `/code-architecture` → return → repo A persists
  - Add repo B → both A and B visible in `RepoExplorer`
  - Start extraction on A → switch tab → return → status continues updating
  - Remove A from Explorer → only B remains

**Regression tests:**
- Existing `02-file-uploader.spec.ts` (if any) selectors may need updates for the relocated UI elements.
- `05-review-queue.spec.ts` should still pass (ReviewDashboard untouched).
- All other Playwright specs should be unaffected (no other components consume `repos` state).

---

## Files Touched

| File | Action | Approx. lines after |
|------|--------|---------------------|
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.tsx` | new | +200 |
| `sources/UI/src/@components/upload-extract/RepoProvider/RepoProvider.test.tsx` | new | +150 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.tsx` | new | +180 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.test.tsx` | new | +120 |
| `sources/UI/src/@components/upload-extract/RepoExplorer/RepoExplorer.scss` | new (moved from FileUploader.scss) | +250 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx` | refactor 678 → ~180 | 180 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` | refactor ~280 → ~150 | 150 |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss` | refactor ~280 → ~30 (moved bulk) | 30 |
| `sources/UI/src/App.tsx` | modify (wrap Provider, drop dead state, render Explorer) | 370 (was 374) |
| `sources/UI/e2e/specs/01-workspace.spec.ts` | new or extend | +80 |
| Backend | unchanged | 0 |
| `services/api.ts` | unchanged | 0 |
| `pages/ReviewDashboard.tsx` | unchanged | 275 |

**Net change summary:**
- New files (production + tests): +900 lines
- FileUploader refactor: ~700 lines removed
- App.tsx: -4 lines
- Approximate net: +200 lines (production) + +270 (new tests)

---

## Open Questions

None — all grill-me questions resolved with recommended options.
