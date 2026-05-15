import { useEffect, useState, useCallback } from "react";
import { wsService } from "../services/api";

export type EnrichedNode = {
  type: string;
  name: string;
  canonical_name: string;
  decision_mode: "LLM_ADJUDICATED" | "NEEDS_REVIEW" | "DETERMINISTIC";
  props: Record<string, unknown>;
};

type EnrichmentEvent =
  | { event: "enrichment_started"; task_id: string; data: { run_id: string } }
  | { event: "enrichment_skipped"; task_id: string; data: { reason: string } }
  | { event: "node_added"; task_id: string; data: EnrichedNode }
  | {
      event: "edge_added";
      task_id: string;
      data: { from: string; to: string; relationship: string };
    }
  | {
      event: "enrichment_complete";
      task_id: string;
      data: { partial: boolean; reason?: string; nodes_added: number };
    }
  | { event: "enrichment_failed"; task_id: string; data: { reason: string } };

export function useEnrichmentWS(taskId: string | null) {
  const [enrichedNodes, setNodes] = useState<EnrichedNode[]>([]);
  const [edges, setEdges] = useState<EnrichmentEvent["data"][]>([]);
  const [status, setStatus] = useState<
    "idle" | "running" | "complete" | "failed" | "skipped"
  >("idle");
  const [partial, setPartial] = useState(false);
  const [partialReason, setPartialReason] = useState<string | null>(null);

  const handle = useCallback(
    (msg: EnrichmentEvent) => {
      if (!taskId || msg.task_id !== taskId) return;
      switch (msg.event) {
        case "enrichment_started":
          setStatus("running");
          break;
        case "enrichment_skipped":
          setStatus("skipped");
          break;
        case "node_added":
          setNodes((prev) => [...prev, msg.data as EnrichedNode]);
          break;
        case "edge_added":
          setEdges((prev) => [...prev, msg.data]);
          break;
        case "enrichment_complete":
          setStatus("complete");
          setPartial(Boolean(msg.data.partial));
          setPartialReason(msg.data.reason || null);
          break;
        case "enrichment_failed":
          setStatus("failed");
          break;
      }
    },
    [taskId],
  );

  useEffect(() => {
    if (!taskId) return;
    const listener = (msg: any) => {
      if (msg && typeof msg === "object" && "event" in msg) {
        handle(msg as EnrichmentEvent);
      }
    };
    wsService.on("message", listener);
    return () => wsService.off("message", listener);
  }, [taskId, handle]);

  return {
    enrichedNodes,
    edges,
    status,
    partial,
    partialReason,
    _inject: handle,
  };
}
