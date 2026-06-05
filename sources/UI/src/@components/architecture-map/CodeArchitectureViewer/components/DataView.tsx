import React, { useState, useRef, useEffect, useMemo } from "react";
import { codeArchitectureAPI } from "../../../../services/api";

interface Entity {
  id: string;
  name: string;
  entity_type?: string;
  language?: string;
  file_path?: string;
  attributes?: Record<string, unknown>;
  [key: string]: unknown;
}

interface Relationship {
  id?: string;
  source_entity_id?: string;
  target_entity_id?: string;
  relationship_type?: string;
  context?: string;
  attributes?: {
    protocol?: string;
    description?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface DataViewProps {
  levelData: { entities: Entity[]; relationships: Relationship[] } | null;
  levelLabel: string;
  architecture: Record<string, unknown> | null;
  markdownCache: React.MutableRefObject<Record<string, string>>;
}

function isDefined(v: unknown): boolean {
  return v !== undefined && v !== null && v !== "" && v !== "Unknown";
}

function cleanEntity(e: Entity) {
  return Object.fromEntries(
    Object.entries({
      id: e.id,
      name: e.name,
      entity_type: e.entity_type,
      language: e.language,
      file_path: e.file_path,
      is_external: e.attributes?.is_external,
    }).filter(([, v]) => isDefined(v)),
  );
}

function cleanRelationship(r: Relationship) {
  return Object.fromEntries(
    Object.entries({
      source: r.source_entity_id,
      target: r.target_entity_id,
      type: r.relationship_type,
      context: r.context,
      protocol: r.attributes?.protocol,
      description: r.attributes?.description,
    }).filter(([, v]) => isDefined(v)),
  );
}

export default function DataView({
  levelData,
  levelLabel,
  architecture,
  markdownCache,
}: DataViewProps) {
  const entities = levelData?.entities ?? [];
  const relationships = levelData?.relationships ?? [];

  const [markdown, setMarkdown] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cleanJson = useMemo(
    () =>
      JSON.stringify(
        {
          level: levelLabel.toLowerCase(),
          entities: entities.map(cleanEntity),
          relationships: relationships.map(cleanRelationship),
        },
        null,
        2,
      ),
    [levelLabel, entities, relationships],
  );

  useEffect(() => {
    if (!architecture) return;

    // Serve from cache if already generated
    const cached = markdownCache.current[levelLabel];
    if (cached) {
      setMarkdown(cached);
      setIsGenerating(false);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setMarkdown("");
    setIsGenerating(true);

    const prompt =
      `Generate a well-structured Markdown document for the ${levelLabel} level of this C4 architecture. ` +
      `Include: a short overview paragraph, a section for each key component/service with its role and technology, ` +
      `a relationships section explaining how they interact, and a summary of architectural patterns. ` +
      `Use proper Markdown formatting with headers (##, ###), bullet lists, and bold labels. ` +
      `Write it as a technical reference document an AI agent could use as context.`;

    let accumulated = "";

    codeArchitectureAPI
      .streamChatWithContext(
        {
          message: prompt,
          architecture: architecture as Record<string, unknown>,
        },
        {
          onDelta: (delta) => {
            accumulated += delta;
            setMarkdown((prev) => prev + delta);
          },
          onComplete: () => {
            markdownCache.current[levelLabel] = accumulated;
            setIsGenerating(false);
          },
          signal: controller.signal,
        },
      )
      .catch((err: unknown) => {
        if (err instanceof Error && err.name !== "AbortError") {
          setMarkdown("Failed to generate. Please refresh and try again.");
        }
        setIsGenerating(false);
      });

    return () => controller.abort();
  }, [levelLabel, architecture]);

  return (
    <div className="data-view">
      <div className="data-view-panel">
        <div className="data-view-panel-header">
          <span className="data-view-panel-title">JSON</span>
          <span className="data-view-panel-meta">
            {entities.length} entities · {relationships.length} relationships
          </span>
        </div>
        <pre className="data-view-code">{cleanJson}</pre>
      </div>

      <div className="data-view-panel">
        <div className="data-view-panel-header">
          <span className="data-view-panel-title">Agent Format</span>
          <span className="data-view-panel-meta">
            {isGenerating ? "Generating…" : "Markdown / LLM context"}
          </span>
        </div>
        <div className="data-view-prose">
          {markdown ? (
            <pre className="data-view-md">
              {markdown}
              {isGenerating && <span className="data-view-cursor" />}
            </pre>
          ) : (
            <p className="data-view-placeholder">
              {isGenerating ? "Generating…" : "Waiting for data…"}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
