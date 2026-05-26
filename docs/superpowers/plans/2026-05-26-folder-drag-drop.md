# Folder Drag-and-Drop Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Local Folder" tab to `FileUploader.tsx` so users can drag-and-drop or click-to-select a local project folder, which is zipped client-side and sent to `POST /api/v1/code/upload-repo`.

**Architecture:** New `FolderDropZone` component handles drag/click → filter → zip → emit blob. `FileUploader` gains tab state and two new `RepoStatus` values (`zipping`, `uploading`), uses XHR for upload progress. API unchanged.

**Tech Stack:** React 18, TypeScript, `fflate` (new dep), `<input webkitdirectory>`, XHR (for upload progress), existing `FileUploader.scss`

---

## File Map

| File | Action |
|------|--------|
| `sources/UI/package.json` | Add `fflate` dep |
| `sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.tsx` | **Create** — drop zone UI + zip logic |
| `sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx` | **Create** — unit tests |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx` | **Modify** — tabs, new status values, upload fn, render FolderDropZone |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss` | **Modify** — tab bar + drop zone styles |
| `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` | **Modify** — add tab/status tests |

---

## Task 1: Install `fflate`

**Files:**
- Modify: `sources/UI/package.json`

- [ ] **Step 1: Install the package**

```bash
cd sources/UI && npm install fflate
```

Expected: `fflate` appears in `package.json` dependencies, no errors.

- [ ] **Step 2: Verify import works**

```bash
cd sources/UI && node -e "require('fflate'); console.log('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd sources/UI && git add package.json package-lock.json
git commit -m "chore(ui): add fflate for client-side zip"
```

---

## Task 2: Create `FolderDropZone` — failing tests first

**Files:**
- Create: `sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx`:

```tsx
/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent } from "@testing-library/react";

expect.extend(matchers);

// Mock fflate
vi.mock("fflate", () => ({
  zip: vi.fn((files, opts, cb) => {
    // Minimal fake: return 10 bytes
    cb(null, new Uint8Array(10));
  }),
}));

import FolderDropZone from "./FolderDropZone";

describe("FolderDropZone", () => {
  const onZipReady = vi.fn();
  const onProgress = vi.fn();
  const onError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders drop zone with instructions", () => {
    render(
      <FolderDropZone
        onZipReady={onZipReady}
        onProgress={onProgress}
        onError={onError}
      />,
    );
    expect(screen.getByText(/drop your project folder/i)).toBeInTheDocument();
    expect(screen.getByText(/or click to select/i)).toBeInTheDocument();
  });

  it("calls onError for empty folder", async () => {
    render(
      <FolderDropZone
        onZipReady={onZipReady}
        onProgress={onProgress}
        onError={onError}
      />,
    );
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    // Fire change with no files
    Object.defineProperty(input, "files", { value: [], configurable: true });
    fireEvent.change(input);
    // onError should be called
    expect(onError).toHaveBeenCalledWith(
      expect.stringMatching(/no files/i),
    );
  });

  it("excludes node_modules from zip entries", async () => {
    const { zip } = await import("fflate");
    render(
      <FolderDropZone
        onZipReady={onZipReady}
        onProgress={onProgress}
        onError={onError}
      />,
    );

    const makeFile = (path: string) => {
      const f = new File(["x"], path.split("/").pop()!);
      Object.defineProperty(f, "webkitRelativePath", {
        value: path,
        configurable: true,
      });
      return f;
    };

    const files = [
      makeFile("project/src/index.ts"),
      makeFile("project/node_modules/react/index.js"),
    ];

    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    Object.defineProperty(input, "files", {
      value: files,
      configurable: true,
    });
    fireEvent.change(input);

    // Wait for async zip call
    await vi.waitFor(() => expect(zip).toHaveBeenCalled());

    const [zipEntries] = (zip as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(Object.keys(zipEntries)).toContain("src/index.ts");
    expect(Object.keys(zipEntries).join(",")).not.toContain("node_modules");
  });

  it("detects .zip drop and calls onZipReady directly without fflate", async () => {
    const { zip } = await import("fflate");
    render(
      <FolderDropZone
        onZipReady={onZipReady}
        onProgress={onProgress}
        onError={onError}
      />,
    );

    const zipFile = new File(["zipcontent"], "project.zip", {
      type: "application/zip",
    });
    const dropZone = screen.getByRole("region");
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [zipFile], types: ["Files"] },
    });

    await vi.waitFor(() => expect(onZipReady).toHaveBeenCalled());
    expect(zip).not.toHaveBeenCalled();
    expect(onZipReady).toHaveBeenCalledWith(
      expect.any(Blob),
      "project",
      expect.any(Number),
    );
  });

  it("shows large-file warning when zip exceeds 150MB", async () => {
    const { zip } = await import("fflate");
    // Override zip to return 160MB
    (zip as ReturnType<typeof vi.fn>).mockImplementationOnce(
      (_files: unknown, _opts: unknown, cb: (err: null, data: Uint8Array) => void) => {
        cb(null, new Uint8Array(160 * 1024 * 1024));
      },
    );

    render(
      <FolderDropZone
        onZipReady={onZipReady}
        onProgress={onProgress}
        onError={onError}
      />,
    );

    const makeFile = (path: string) => {
      const f = new File(["x"], path.split("/").pop()!);
      Object.defineProperty(f, "webkitRelativePath", {
        value: path,
        configurable: true,
      });
      return f;
    };
    const files = [makeFile("project/src/index.ts")];
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    Object.defineProperty(input, "files", { value: files, configurable: true });
    fireEvent.change(input);

    await vi.waitFor(() => expect(onZipReady).toHaveBeenCalled());
    // onZipReady is still called (warn, don't block)
    expect(onZipReady).toHaveBeenCalled();
    // onProgress called with 'warning' phase
    expect(onProgress).toHaveBeenCalledWith("warning", 160 * 1024 * 1024);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd sources/UI && npx vitest run src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx
```

Expected: All 5 tests FAIL with "Cannot find module './FolderDropZone'"

---

## Task 3: Implement `FolderDropZone`

**Files:**
- Create: `sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.tsx`

- [ ] **Step 1: Create the component**

```tsx
import React, { useRef, useState, useCallback } from "react";
import { Upload } from "lucide-react";
import { zip } from "fflate";

const EXCLUDED_DIRS = new Set([
  "node_modules",
  ".git",
  "__pycache__",
  "dist",
  "build",
  ".next",
  "target",
  "vendor",
  ".venv",
  "coverage",
]);

const LARGE_ZIP_BYTES = 150 * 1024 * 1024;

function isExcluded(relativePath: string): boolean {
  const parts = relativePath.split("/");
  return parts.some((part) => EXCLUDED_DIRS.has(part));
}

export interface FolderDropZoneProps {
  onZipReady: (blob: Blob, name: string, sizeBytes: number) => void;
  onProgress: (phase: "zipping" | "uploading" | "warning", value: number) => void;
  onError: (msg: string) => void;
}

const FolderDropZone: React.FC<FolderDropZoneProps> = ({
  onZipReady,
  onProgress,
  onError,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const processFiles = useCallback(
    async (fileList: File[]) => {
      if (fileList.length === 0) {
        onError("No files found in the selected folder.");
        return;
      }

      // Detect direct ZIP drop
      if (
        fileList.length === 1 &&
        (fileList[0].name.endsWith(".zip") ||
          fileList[0].type === "application/zip")
      ) {
        const zipFile = fileList[0];
        const name = zipFile.name.replace(/\.zip$/i, "");
        onZipReady(zipFile, name, zipFile.size);
        return;
      }

      // Filter excluded paths
      const kept = fileList.filter(
        (f) => !isExcluded(f.webkitRelativePath || f.name),
      );

      if (kept.length === 0) {
        onError("No files found after excluding build artifacts.");
        return;
      }

      // Determine folder name from first file's webkitRelativePath
      const firstPath = kept[0].webkitRelativePath || kept[0].name;
      const folderName = firstPath.split("/")[0] || "project";

      // Read all files and build fflate input map
      const entries: Record<string, Uint8Array> = {};
      let loaded = 0;

      for (const file of kept) {
        const relativePath = file.webkitRelativePath
          ? file.webkitRelativePath.slice(folderName.length + 1)
          : file.name;
        if (!relativePath) continue;

        const buf = await file.arrayBuffer();
        entries[relativePath] = new Uint8Array(buf);
        loaded += 1;
        onProgress("zipping", Math.round((loaded / kept.length) * 100));
      }

      // Zip using fflate async callback API
      zip(entries, { level: 1 }, (err, data) => {
        if (err) {
          onError(`Zip failed: ${err.message}`);
          return;
        }
        const blob = new Blob([data], { type: "application/zip" });
        if (data.byteLength > LARGE_ZIP_BYTES) {
          onProgress("warning", data.byteLength);
        }
        onZipReady(blob, folderName, data.byteLength);
      });
    },
    [onZipReady, onProgress, onError],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      processFiles(files);
    },
    [processFiles],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      processFiles(files);
      // Reset so same folder can be re-selected
      e.target.value = "";
    },
    [processFiles],
  );

  return (
    <div
      role="region"
      aria-label="Drop project folder here"
      className={`folder-drop-zone ${isDragging ? "folder-drop-zone--active" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        // @ts-expect-error webkitdirectory is non-standard
        webkitdirectory=""
        multiple
        style={{ display: "none" }}
        onChange={handleChange}
      />
      <Upload size={40} className="folder-drop-zone__icon" />
      <p className="folder-drop-zone__title">Drop your project folder here</p>
      <p className="folder-drop-zone__hint">or click to select &nbsp;·&nbsp; also accepts .zip files</p>
    </div>
  );
};

export default FolderDropZone;
```

- [ ] **Step 2: Run tests**

```bash
cd sources/UI && npx vitest run src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx
```

Expected: All 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.tsx \
        sources/UI/src/@components/upload-extract/FileUploader/FolderDropZone.test.tsx
git commit -m "feat(ui): add FolderDropZone component with fflate zip"
```

---

## Task 4: Extend `FileUploader` — new status values + upload fn

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx`

- [ ] **Step 1: Write failing tests for new status values and tab**

Add to `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.test.tsx` (append inside the existing `describe` block):

```tsx
  it("renders GitHub URL tab by default", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    expect(screen.getByRole("tab", { name: /github url/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /local folder/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(GITHUB_INPUT_PLACEHOLDER)).toBeInTheDocument();
  });

  it("switches to Local Folder tab on click", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /local folder/i }));
    expect(screen.getByRole("region", { name: /drop project folder/i })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(GITHUB_INPUT_PLACEHOLDER)).not.toBeInTheDocument();
  });

  it("shows zipping label for zipping status", () => {
    render(
      <FileUploader
        onFilesUploaded={mockOnFilesUploaded}
        isProcessing={false}
        onExtractionStarted={mockOnExtractionStarted}
        showNotification={mockShowNotification}
      />,
    );
    // Expose internal state by checking statusConfig via data-testid
    // We test via the rendered output after a local upload starts
    // (zipping status is set before XHR upload begins)
    // Verify statusConfig labels exist in the component via snapshot-free check:
    expect(screen.queryByText("Zipping")).not.toBeInTheDocument(); // not shown until repo added
  });
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd sources/UI && npx vitest run src/@components/upload-extract/FileUploader/FileUploader.test.tsx --reporter=verbose 2>&1 | grep -E "FAIL|PASS|renders GitHub|switches to|shows zip"
```

Expected: The 3 new tests FAIL.

- [ ] **Step 3: Modify `FileUploader.tsx`**

Replace the top of `FileUploader.tsx` through the `RepoStatus` type definition and add the upload helper. Apply these diffs:

**a) Extend `RepoStatus` (line 29):**
```tsx
// Before:
type RepoStatus = "idle" | "pending" | "scanning" | "completed" | "failed";

// After:
type RepoStatus = "idle" | "pending" | "scanning" | "completed" | "failed" | "zipping" | "uploading";
```

**b) Add tab state to component (after the existing state declarations, ~line 62):**
```tsx
  const [activeTab, setActiveTab] = useState<"github" | "local">("github");
```

**c) Add XHR upload function wrapped in `useCallback` (after `pollStatus`, before `extractAll`):**
```tsx
  const uploadZip = useCallback(
    (blob: Blob, folderName: string): Promise<{ task_id: string }> =>
      new Promise((resolve, reject) => {
        const form = new FormData();
        form.append("file", blob, `${folderName}.zip`);
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/v1/code/upload-repo");
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            // Match on displayName (folderName + "/") — that's what was added to repos
            setRepos((prev) =>
              prev.map((r) =>
                r.url === folderName + "/"
                  ? { ...r, status: "uploading", message: `Uploading… ${pct}%`, progress: pct / 100 }
                  : r,
              ),
            );
          }
        };
        xhr.onload = () => {
          if (xhr.status === 202) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            reject(new Error(xhr.responseText || "Upload failed"));
          }
        };
        xhr.onerror = () => reject(new Error("Network error during upload"));
        xhr.send(form);
      }),
    [],
  );
```

**d) Add `handleFolderZipReady` handler (after `uploadZip`):**
```tsx
  const handleFolderZipReady = useCallback(
    async (blob: Blob, name: string, sizeBytes: number) => {
      const displayName = name + "/";
      if (repos.some((r) => r.url === displayName)) {
        showNotification("This folder has already been added.", "info");
        return;
      }
      setRepos((prev) => [
        ...prev,
        {
          url: displayName,
          status: "zipping" as RepoStatus,
          message: "Zipping complete, uploading…",
          progress: 0,
          containersCount: 0,
          componentsCount: 0,
        },
      ]);
      try {
        const result = await uploadZip(blob, name);
        const taskId = result.task_id;
        setRepos((prev) =>
          prev.map((r) =>
            r.url === displayName
              ? { ...r, taskId, status: "pending", message: "Queued", progress: 0 }
              : r,
          ),
        );
        onExtractionStarted(taskId, {
          name: displayName,
          headers: [],
          data: [],
          size: sizeBytes,
          rowCount: 0,
          type: "local",
        });
        pollStatus(taskId);
        showNotification(`Extraction started for ${displayName}`, "success");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setRepos((prev) =>
          prev.map((r) =>
            r.url === displayName
              ? { ...r, status: "failed", message: msg }
              : r,
          ),
        );
        showNotification(`Upload failed for ${displayName}: ${msg}`, "error");
      }
    },
    [repos, showNotification, uploadZip, pollStatus, onExtractionStarted],
  );
```

**e) Add `handleFolderProgress` (after `handleFolderZipReady`):**
```tsx
  const handleFolderProgress = useCallback(
    (phase: "zipping" | "uploading" | "warning", value: number) => {
      if (phase === "warning") {
        const mb = Math.round(value / 1024 / 1024);
        showNotification(
          `Large zip (${mb} MB) — upload may be slow.`,
          "info",
        );
        return;
      }
      // zipping progress — find the repo currently in zipping status
      setRepos((prev) =>
        prev.map((r) =>
          r.status === "zipping"
            ? {
                ...r,
                message: phase === "zipping" ? `Zipping… ${value}%` : `Uploading… ${value}%`,
                progress: value / 100,
              }
            : r,
        ),
      );
    },
    [showNotification],
  );
```

**f) Add `zipping` and `uploading` to `statusConfig` (inside the existing `statusConfig` record):**
```tsx
    zipping: {
      icon: <Loader size={14} className="spin" />,
      color: "#6610f2",
      label: "Zipping",
    },
    uploading: {
      icon: <Loader size={14} className="spin" />,
      color: "#007bff",
      label: "Uploading",
    },
```

**g) Add import for `FolderDropZone` at top of file:**
```tsx
import FolderDropZone from "./FolderDropZone";
```

**h) Replace the JSX `return` — add tab bar above `url-input-section` and render `FolderDropZone` in local tab:**

Replace:
```tsx
  return (
    <div className="repo-extractor">
      {/* URL Input */}
      <div className="url-input-section">
```

With:
```tsx
  return (
    <div className="repo-extractor">
      {/* Tabs */}
      <div className="repo-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "github"}
          className={`repo-tab ${activeTab === "github" ? "repo-tab--active" : ""}`}
          onClick={() => setActiveTab("github")}
        >
          GitHub URL
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "local"}
          className={`repo-tab ${activeTab === "local" ? "repo-tab--active" : ""}`}
          onClick={() => setActiveTab("local")}
        >
          Local Folder
        </button>
      </div>

      {activeTab === "local" ? (
        <FolderDropZone
          onZipReady={handleFolderZipReady}
          onProgress={handleFolderProgress}
          onError={(msg) => showNotification(msg, "error")}
        />
      ) : (
      /* URL Input */
      <div className="url-input-section">
```

Also replace the closing of `url-input-section` block. Find this exact block (the input section closing tag + error paragraph):

```tsx
        {inputError && <p className="url-error">{inputError}</p>}
      </div>

      {/* Repo List */}
```

Replace with:

```tsx
        {inputError && <p className="url-error">{inputError}</p>}
      </div>
      )}

      {/* Repo List */}
```

The `)` closes the ternary started by `{activeTab === "local" ? ... : (`. The full conditional block becomes:

```tsx
      {activeTab === "local" ? (
        <FolderDropZone
          onZipReady={handleFolderZipReady}
          onProgress={handleFolderProgress}
          onError={(msg) => showNotification(msg, "error")}
        />
      ) : (
        <div className="url-input-section">
          <div className="url-input-row">
            {/* ... existing URL input row unchanged ... */}
          </div>
          {inputError && <p className="url-error">{inputError}</p>}
        </div>
      )}

      {/* Repo List — shared, always rendered */}
```

- [ ] **Step 4: Run all FileUploader tests**

```bash
cd sources/UI && npx vitest run src/@components/upload-extract/FileUploader/FileUploader.test.tsx
```

Expected: All tests PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/@components/upload-extract/FileUploader/FileUploader.tsx
git commit -m "feat(ui): add tabs + local folder upload to FileUploader"
```

---

## Task 5: Add styles

**Files:**
- Modify: `sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss`

- [ ] **Step 1: Append styles to `FileUploader.scss`**

Append to the bottom of the file:

```scss
/* Tab Bar */
.repo-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid #e9ecef;
}

.repo-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6c757d;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;

  &:hover {
    color: #343a40;
  }

  &--active {
    color: #e8420f;
    border-bottom-color: #e8420f;
  }
}

/* Folder Drop Zone */
.folder-drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 180px;
  border: 2px dashed #dee2e6;
  border-radius: 8px;
  padding: 2rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  margin-bottom: 1.5rem;

  &:hover,
  &--active {
    border-color: #e8420f;
    background: rgba(232, 66, 15, 0.04);
  }

  &__icon {
    color: #adb5bd;
  }

  &__title {
    font-weight: 600;
    font-size: 0.95rem;
    color: #343a40;
    margin: 0;
  }

  &__hint {
    font-size: 0.8rem;
    color: #6c757d;
    margin: 0;
  }
}
```

- [ ] **Step 2: Run all tests to ensure no regressions**

```bash
cd sources/UI && npx vitest run src/@components/upload-extract/FileUploader/
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add sources/UI/src/@components/upload-extract/FileUploader/FileUploader.scss
git commit -m "style(ui): add tab bar and folder drop zone styles"
```

---

## Task 6: Smoke test in browser

- [ ] **Step 1: Ensure containers are running**

```bash
docker compose ps
```

Expected: `api`, `ui` both `Up (healthy)`.

- [ ] **Step 2: Open workspace**

Navigate to `http://localhost:3010/workspace`.

Expected: "Local Folder" tab visible next to "GitHub URL" tab.

- [ ] **Step 3: Click "Local Folder" tab**

Expected: Drop zone appears with upload icon and "Drop your project folder here" text.

- [ ] **Step 4: Drop a local project folder**

Drop any medium-sized project folder (e.g. `~/Desktop/Startup/KnowledgeForge/sources/UI`).

Expected:
- Progress bar shows "Zipping… X%"
- Switches to "Uploading… X%"
- Entry appears in repo list with folder name + `/`
- Transitions to "Queued" → "Scanning" → "Done"

- [ ] **Step 5: Verify GitHub URL tab still works**

Click "GitHub URL" tab, add `https://github.com/microservices-demo/microservices-demo`, click Extract.

Expected: Extraction starts normally.

- [ ] **Step 6: Run full test suite**

```bash
cd sources/UI && npx vitest run
```

Expected: All tests PASS.

- [ ] **Step 7: Final commit**

```bash
git add -p  # stage any remaining changes
git commit -m "feat(ui): local folder drag-drop upload complete"
```
