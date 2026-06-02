/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

expect.extend(matchers);
afterEach(cleanup);

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
    expect(onError).toHaveBeenCalledWith(expect.stringMatching(/no files/i));
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
      (
        _files: unknown,
        _opts: unknown,
        cb: (err: null, data: Uint8Array) => void,
      ) => {
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
