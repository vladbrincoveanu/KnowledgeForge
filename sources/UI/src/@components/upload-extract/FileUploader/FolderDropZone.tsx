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

      const readFileAsUint8Array = (file: File): Promise<Uint8Array> =>
        new Promise((resolve, reject) => {
          // Prefer arrayBuffer when available (modern browsers); fall back to
          // FileReader for environments (e.g. jsdom) that don't implement it.
          if (typeof file.arrayBuffer === "function") {
            file
              .arrayBuffer()
              .then((buf) => resolve(new Uint8Array(buf)))
              .catch(reject);
          } else {
            const reader = new FileReader();
            reader.onload = () =>
              resolve(new Uint8Array(reader.result as ArrayBuffer));
            reader.onerror = () => reject(reader.error);
            reader.readAsArrayBuffer(file);
          }
        });

      for (const file of kept) {
        const relativePath = file.webkitRelativePath
          ? file.webkitRelativePath.slice(folderName.length + 1)
          : file.name;
        if (!relativePath) continue;

        const data = await readFileAsUint8Array(file);
        entries[relativePath] = data;
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
