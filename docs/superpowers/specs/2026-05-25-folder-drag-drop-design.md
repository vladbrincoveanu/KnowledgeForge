# Spec: Local Folder Drag-and-Drop Upload

**Date:** 2026-05-25  
**Branch:** feat/folder-drag-drop  
**Status:** Approved

---

## Summary

Add a "Local Folder" tab to `FileUploader.tsx` that lets users drag-and-drop or click-to-select a local project folder. The folder is zipped client-side (excluding noise dirs) and sent to the existing `POST /api/v1/code/upload-repo` endpoint. No API changes required.

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Tabs UI ("GitHub URL" / "Local Folder") | Clean separation, no layout disruption |
| 2 | `fflate` async callback API (not Worker) | No Vite worker config needed; non-blocking via setTimeout chunks |
| 3 | Auto-exclude noise dirs | Prevents 500MB+ zips from OOM-ing the API |
| 4 | Warn at 150MB post-zip, don't block | UX over hard gates; large repos still valid |
| 5 | Drop `.zip` directly → skip re-zip | Avoids double-compression, better UX |
| 6 | Shared repo list across tabs | Single list, tab only controls input method |
| 7 | Display name = folder name | More meaningful than zip filename |
| 8 | Two new progress states: `zipping` + `uploading` | Large repos need per-phase feedback |

---

## Excluded Directories (client-side, before zip)

```
node_modules/   .git/         __pycache__/
dist/           build/        .next/
target/         vendor/       .venv/
*.egg-info/     coverage/
```

---

## Module Design

### Module: `FolderDropZone`
- **Responsibility:** Accept folder drag-drop or `<input webkitdirectory>` click, zip contents via `fflate`, emit `{ blob: Blob, name: string, sizeBytes: number }`
- **Interface:** `onZipReady(blob, name, sizeBytes): void` | `onProgress(phase: 'zipping'|'uploading', pct: number): void` | `onError(msg: string): void`
- **Dependencies:** `fflate` (new dep)
- **Size target:** ≤200 lines

### Module: `FileUploader` (modified)
- **Responsibility:** Tab state, repo list (shared), calls `FolderDropZone` for local tab, calls existing GitHub URL flow for GitHub tab
- **Interface:** unchanged props (`onFilesUploaded`, `isProcessing`, `onExtractionStarted`, `showNotification`)
- **Dependencies:** `FolderDropZone`, existing `codeArchitectureAPI`
- **Size target:** ≤300 lines (currently 424 — refactor tab split reduces it)

---

## RepoStatus Extension

```ts
// Add to existing RepoStatus union:
type RepoStatus = "idle" | "pending" | "scanning" | "completed" | "failed"
               | "zipping" | "uploading";   // NEW
```

`statusConfig` record must include entries for both new states.

---

## Flow: Local Folder

```
User drops folder / clicks → FolderDropZone
  → filter excluded dirs
  → fflate async zip() with progress callback → "Zipping… X%"
  → if sizeBytes > 150MB: show warning toast (don't block)
  → POST /api/v1/code/upload-repo (multipart) with XHR progress → "Uploading… X%"
  → on 202: add to repo list as "pending", start pollStatus()
  → same polling + WS path as GitHub repos
```

## Flow: Direct ZIP Drop

```
User drops .zip file → FolderDropZone detects .zip
  → skip fflate entirely
  → POST /api/v1/code/upload-repo directly
  → "Uploading… X%" → pending → scanning → completed
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/@components/upload-extract/FileUploader/FileUploader.tsx` | Add tab state; render `FolderDropZone` in Local tab; extend `RepoStatus` |
| `src/@components/upload-extract/FileUploader/FolderDropZone.tsx` | New component |
| `src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx` | New tests |
| `src/@components/upload-extract/FileUploader/FileUploader.scss` | Tab + dropzone styles |
| `sources/UI/package.json` | Add `fflate` |

**API: no changes.**

---

## Tests (FolderDropZone.test.tsx)

1. Renders drop zone with correct text
2. Calls `onZipReady` after folder drop (mock `fflate`)
3. Excludes `node_modules` from zip entries
4. Detects `.zip` drop → skips fflate, calls `onZipReady` with original blob
5. Calls `onError` on empty folder
6. Shows 150MB warning (mock sizeBytes > 150MB)

## Tests (FileUploader.test.tsx additions)

7. Tab switch renders correct input section
8. `zipping` status shows correct icon + label
9. `uploading` status shows correct icon + label
10. Shared repo list: GitHub + local folder entries both appear

---

## Out of Scope

- Private repos / auth for local uploads
- Streaming ZIP upload (chunked transfer) — API doesn't support it
- Mobile drag-and-drop (webkitdirectory not supported on iOS)
- Cancellation of in-progress zip/upload
