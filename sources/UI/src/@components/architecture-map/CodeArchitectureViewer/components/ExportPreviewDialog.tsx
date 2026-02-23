import React, { useMemo, useState } from 'react';

interface ExportPreviewDialogProps {
  open: boolean;
  format: 'structurizr' | 'mermaid';
  filename: string;
  content: string;
  onClose: () => void;
  onDownload: () => void;
}

function parseMermaidPreview(content: string) {
  const lines = content.split('\n').map(line => line.trim());
  const systems: Array<{ id: string; name: string; kind: 'system' | 'external' }> = [];
  const rels: Array<{ source: string; target: string; label: string }> = [];

  const sysRe = /^System\(([^,]+),\s*"([^"]+)"/i;
  const extRe = /^System_Ext\(([^,]+),\s*"([^"]+)"/i;
  const relRe = /^Rel\(([^,]+),\s*([^,]+),\s*"([^"]*)"/i;

  lines.forEach(line => {
    const sys = line.match(sysRe);
    if (sys) {
      systems.push({ id: sys[1].trim(), name: sys[2].trim(), kind: 'system' });
      return;
    }
    const ext = line.match(extRe);
    if (ext) {
      systems.push({ id: ext[1].trim(), name: ext[2].trim(), kind: 'external' });
      return;
    }
    const rel = line.match(relRe);
    if (rel) {
      rels.push({
        source: rel[1].trim(),
        target: rel[2].trim(),
        label: rel[3].trim() || 'uses',
      });
    }
  });

  const nameById = new Map(systems.map(system => [system.id, system.name]));
  return {
    systems,
    rels: rels.map(rel => ({
      ...rel,
      sourceName: nameById.get(rel.source) || rel.source,
      targetName: nameById.get(rel.target) || rel.target,
    })),
  };
}

export default function ExportPreviewDialog({
  open,
  format,
  filename,
  content,
  onClose,
  onDownload,
}: ExportPreviewDialogProps) {
  const [copied, setCopied] = useState(false);

  const mermaidPreview = useMemo(
    () => (format === 'mermaid' ? parseMermaidPreview(content) : null),
    [format, content]
  );

  if (!open) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="export-preview-backdrop" onClick={onClose}>
      <div className="export-preview-modal" onClick={e => e.stopPropagation()}>
        <div className="export-preview-header">
          <div>
            <h3>{format === 'mermaid' ? 'Mermaid Preview' : 'Structurizr Preview'}</h3>
            <p>{filename}</p>
          </div>
          <button className="export-preview-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="export-preview-actions">
          <button type="button" onClick={handleCopy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={onDownload}>
            Download
          </button>
        </div>

        {format === 'mermaid' && mermaidPreview ? (
          <div className="mermaid-inline-preview">
            <div className="mermaid-nodes">
              {mermaidPreview.systems.map(system => (
                <div
                  key={system.id}
                  className={`mermaid-node ${
                    system.kind === 'system' ? 'mermaid-node-system' : 'mermaid-node-external'
                  }`}
                >
                  {system.name}
                </div>
              ))}
            </div>
            <div className="mermaid-rels">
              {mermaidPreview.rels.map((rel, idx) => (
                <div key={`${rel.source}-${rel.target}-${idx}`} className="mermaid-rel">
                  {rel.sourceName} → {rel.targetName} ({rel.label})
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <pre className="export-preview-code">{content}</pre>
      </div>
    </div>
  );
}

