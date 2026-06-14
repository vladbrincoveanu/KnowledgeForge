import React, { useEffect, useRef, useState } from "react";
import type { ArchitectureChatMessage } from "../../../../services/api";
import FormattedDetailValue from "./FormattedDetailValue";

// ── Compliance formatting helpers ─────────────────────────────────────────────

const complianceStatusLabels: Record<string, string> = {
  EXCELLENT: "Excellent",
  COMPLIANT: "Compliant",
  AT_RISK: "At risk",
  NON_COMPLIANT: "Non-compliant",
  UNKNOWN: "Unknown",
};

const complianceFactorLabels: Record<string, string> = {
  sensitive_data_low_tier: "Sensitive data stored in a low-tier system",
  sensitive_data_no_owner: "Sensitive data without an owner",
  critical_service_no_owner: "Critical service without an owner",
  no_active_maintainers: "No active maintainers",
  deprecated_with_sensitive_data: "Deprecated service with sensitive data",
  single_point_of_failure: "Single maintainer for a Tier 1 service",
};

const nodeTypeLabels: Record<string, string> = {
  system: "System",
  container: "Container",
  component: "Component",
  person: "Actor",
  external_system: "External System",
  external_service: "External Dependency",
};

function formatComplianceStatus(status?: string) {
  if (!status) return "";
  return complianceStatusLabels[status] || status.replace(/_/g, " ");
}

function formatComplianceFactor(factor: string) {
  const cleaned = factor.trim();
  const label = complianceFactorLabels[cleaned];
  if (label) return label;
  const spaced = cleaned.replace(/_/g, " ");
  return spaced ? `${spaced[0].toUpperCase()}${spaced.slice(1)}` : "";
}

function formatComplianceFactors(factors?: string[]): string[] {
  return (factors || [])
    .map(formatComplianceFactor)
    .filter((v): v is string => Boolean(v));
}

function humanizeIdentifier(value?: string) {
  if (!value) return "";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatNodeTypeLabel(type?: string) {
  if (!type) return "";
  return nodeTypeLabels[type] || humanizeIdentifier(type);
}

function formatDocQuality(dq: any): {
  score: number | null;
  tier: string | null;
} {
  if (!dq) return { score: null, tier: null };
  if (typeof dq === "object") {
    return {
      score: dq.score ?? dq.total_score ?? null,
      tier: dq.tier ?? dq.quality_tier ?? null,
    };
  }
  if (typeof dq === "number") return { score: dq, tier: null };
  return { score: null, tier: String(dq) };
}

// ── Row helpers ───────────────────────────────────────────────────────────────

interface RowProps {
  label: string;
  tooltip?: string;
  children: React.ReactNode;
  className?: string;
}

function DetailRow({ label, tooltip, children, className = "" }: RowProps) {
  return (
    <div className={`detail-row ${className}`}>
      <div className="detail-heading">
        <span className="detail-label">{label}</span>
        {tooltip && (
          <span
            className="tooltip-hint"
            tabIndex={0}
            aria-label={`Help for ${label}`}
          >
            i<span className="tooltip-content">{tooltip}</span>
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

interface NodeDetailsPanelProps {
  selectedNode: any;
  onClose: () => void;
  nodeDescription: string;
  isNodeLoading: boolean;
  chatMessages: ArchitectureChatMessage[];
  isChatLoading: boolean;
  onSendChat: (message: string) => Promise<void>;
}

export default function NodeDetailsPanel({
  selectedNode,
  onClose,
  nodeDescription,
  isNodeLoading,
  chatMessages,
  isChatLoading,
  onSendChat,
}: NodeDetailsPanelProps) {
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const lastChatMessage = chatMessages[chatMessages.length - 1];
  const chatStatusLabel = isChatLoading ? "Preparing a response..." : null;
  const chatStatus = chatStatusLabel ? (
    <div className="chat-status" role="status" aria-live="polite">
      <span className="chat-status-indicator" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>{chatStatusLabel}</span>
    </div>
  ) : null;

  useEffect(() => {
    if (typeof chatEndRef.current?.scrollIntoView === "function") {
      chatEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [
    chatMessages.length,
    isChatLoading,
    lastChatMessage?.content,
    lastChatMessage?.streaming,
  ]);

  const handleSendChat = async () => {
    const nextMessage = chatInput.trim();
    if (!nextMessage) return;
    setChatInput("");
    await onSendChat(nextMessage);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendChat();
    }
  };

  const nodeType = selectedNode?.type;
  const attrs = selectedNode?.attributes || {};
  const systemAttributes = nodeType === "system" ? attrs : null;
  const containerMeta = selectedNode?.containerMeta || {};
  const ownerValue =
    systemAttributes?.owner_team ||
    systemAttributes?.owner ||
    containerMeta.owner_team ||
    containerMeta.owner ||
    attrs.owner;
  const statusValue =
    systemAttributes?.status || containerMeta.status || attrs.status;
  const tierValue =
    systemAttributes?.criticality ||
    systemAttributes?.tier ||
    containerMeta.tier ||
    attrs.tier;
  const dataClassValue =
    systemAttributes?.data_class ||
    containerMeta.data_class ||
    attrs.data_class;
  const activeExpertsValue =
    systemAttributes?.active_experts ??
    containerMeta.active_experts ??
    attrs.active_experts;

  const complianceStatus =
    systemAttributes?.compliance ??
    containerMeta.compliance ??
    attrs.compliance;
  const complianceStatusLabel = formatComplianceStatus(complianceStatus);
  const complianceConfidence =
    systemAttributes?.compliance_confidence ??
    containerMeta.compliance_confidence ??
    attrs.compliance_confidence;
  const complianceConfidencePercent =
    complianceConfidence != null
      ? Math.round(100 * complianceConfidence)
      : undefined;
  const complianceFactors = formatComplianceFactors(
    systemAttributes?.compliance_factors ??
      containerMeta.compliance_factors ??
      attrs.compliance_factors,
  );

  const docQuality = formatDocQuality(systemAttributes?.documentation_quality);
  const deploymentTargets: string[] =
    systemAttributes?.deployment_targets || [];
  const isExternalDependencyNode =
    String(nodeType || "").startsWith("external") || Boolean(attrs.is_external);
  const nodeTypeLabel = isExternalDependencyNode
    ? "External Dependency"
    : formatNodeTypeLabel(nodeType);

  // Person/actor node — dedicated panel
  if (nodeType === "person") {
    const actorDesc = attrs.description || attrs.role || "";
    return (
      <aside className="node-details-panel chat-style">
        <div className="chat-header">
          <div className="chat-title">
            <h3>{selectedNode?.name || selectedNode?.label || "Actor"}</h3>
            <span className="chat-subtitle">Actor / Person</span>
          </div>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="chat-messages">
          {(nodeDescription || isNodeLoading) && (
            <div className="chat-message assistant">
              <div className="message-content">
                {isNodeLoading ? (
                  "Loading description..."
                ) : (
                  <FormattedDetailValue
                    value={nodeDescription}
                    preserveWhitespace
                  />
                )}
              </div>
            </div>
          )}
          {actorDesc && !nodeDescription && !isNodeLoading && (
            <div className="chat-message assistant">
              <div className="message-content">
                <FormattedDetailValue value={actorDesc} preserveWhitespace />
              </div>
            </div>
          )}
          {chatMessages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`chat-message ${message.role}${message.streaming ? " streaming" : ""}`}
            >
              <div className="message-content">
                <FormattedDetailValue
                  value={message.content}
                  preserveWhitespace
                />
              </div>
            </div>
          ))}
          <div className="chat-properties">
            <DetailRow
              label="Type"
              tooltip="C4 actor type: person (human user) or system (automated actor)."
            >
              <span className="detail-value">Actor / Person</span>
            </DetailRow>
            {attrs.role && (
              <DetailRow label="Role">
                <span className="detail-value">{attrs.role}</span>
              </DetailRow>
            )}
            {attrs.detected_from && (
              <DetailRow label="Detected From">
                <span className="detail-value">{attrs.detected_from}</span>
              </DetailRow>
            )}
            {attrs.detection_method && (
              <DetailRow label="Detection Method">
                <span className="detail-value">{attrs.detection_method}</span>
              </DetailRow>
            )}
            {attrs.evidence && (
              <DetailRow label="Evidence">
                <FormattedDetailValue
                  value={attrs.evidence}
                  preserveWhitespace
                />
              </DetailRow>
            )}
          </div>
          <div ref={chatEndRef} aria-hidden="true" />
        </div>

        {/* Chat Input */}
        <div className="chat-input-container">
          {chatStatus}
          <div className="chat-input-wrapper">
            <textarea
              placeholder="Ask about this node..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button
              className="send-btn"
              aria-label="Send chat message"
              onClick={handleSendChat}
              disabled={!chatInput.trim() || isChatLoading}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
    );
  }

  // No node selected - show welcome message + chat
  if (!selectedNode) {
    return (
      <aside className="node-details-panel chat-style">
        <div className="chat-header">
          <div className="chat-title">
            <h3>Inspector</h3>
            <span className="chat-subtitle">Click a node to inspect</span>
          </div>
        </div>
        <div className="chat-messages">
          <div className="chat-message assistant">
            <div className="message-content">
              <p>
                Select any node in the graph to view its properties, metrics,
                and relationships.
              </p>
              <p className="hint-text">
                You can also click on edges to see relationship details.
              </p>
            </div>
          </div>
          {chatMessages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`chat-message ${message.role}${message.streaming ? " streaming" : ""}`}
            >
              <div className="message-content">
                <FormattedDetailValue
                  value={message.content}
                  preserveWhitespace
                />
              </div>
            </div>
          ))}
          <div ref={chatEndRef} aria-hidden="true" />
        </div>

        {/* Chat Input */}
        <div className="chat-input-container">
          {chatStatus}
          <div className="chat-input-wrapper">
            <textarea
              placeholder="Ask me anything..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button
              className="send-btn"
              aria-label="Send chat message"
              onClick={handleSendChat}
              disabled={!chatInput.trim() || isChatLoading}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="node-details-panel chat-style">
      <div className="chat-header">
        <div className="chat-avatar" />
        <div className="chat-title">
          <h3>
            {selectedNode?.name ||
              selectedNode?.label ||
              selectedNode?.id ||
              "Node Details"}
          </h3>
          <span className="chat-subtitle">
            {nodeTypeLabel || "Node Details"}
          </span>
        </div>
        <button className="close-btn" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="chat-messages">
        {/* Description */}
        {(nodeDescription || isNodeLoading) && (
          <div className="detail-row description-row">
            <FormattedDetailValue
              value={isNodeLoading ? "Loading description..." : nodeDescription}
              className="description-text"
              preserveWhitespace
            />
          </div>
        )}

        {/* Purpose/description (when no LLM description yet) */}
        {!nodeDescription &&
          !isNodeLoading &&
          (systemAttributes?.purpose ||
            systemAttributes?.description ||
            attrs.description) && (
            <div className="detail-row description-row">
              <FormattedDetailValue
                value={
                  systemAttributes?.purpose ||
                  systemAttributes?.description ||
                  attrs.description
                }
                className="description-text"
                preserveWhitespace
              />
            </div>
          )}

        {/* Owner field (system only) */}
        {nodeType === "system" && (
          <DetailRow
            label="Owner"
            tooltip="The team or individual responsible for this system. If unassigned, add a CODEOWNERS file or specify the team in the README."
          >
            <span className="detail-value">{ownerValue || "Unassigned"}</span>
            {(
              (systemAttributes?.owner_contributors ||
                attrs.owner_contributors) ??
              []
            ).length > 0 && (
              <div className="detail-sub">
                Contributors:{" "}
                {(
                  systemAttributes?.owner_contributors ||
                  attrs.owner_contributors ||
                  []
                )
                  .slice(0, 3)
                  .join(", ")}
                {(
                  systemAttributes?.owner_contributors ||
                  attrs.owner_contributors ||
                  []
                ).length > 3 && "…"}
              </div>
            )}
          </DetailRow>
        )}

        {/* Actors list (system node) */}
        {nodeType === "system" && (
          <DetailRow
            label="Actors"
            tooltip="Human users or external systems that directly interact with this system."
          >
            <FormattedDetailValue
              value={
                (systemAttributes?.actors || []).length > 0
                  ? (systemAttributes?.actors || []).map(
                      (actor: any) =>
                        `${actor.name}${actor.description ? ` - ${actor.description}` : ""}`,
                    )
                  : "Not detected"
              }
            />
          </DetailRow>
        )}

        {/* Service count */}
        {nodeType === "system" && systemAttributes?.service_count > 0 && (
          <DetailRow
            label="Services"
            tooltip="Total number of deployable containers/microservices detected in this system."
          >
            <span className="detail-value">
              {systemAttributes.service_count} containers
            </span>
          </DetailRow>
        )}

        {/* Business Domain */}
        {nodeType === "system" && (
          <DetailRow
            label="Business Domain"
            tooltip="The business domain this system belongs to (e.g. Commerce, Identity, Logistics). Detected from service name, README, and package manifests."
          >
            <span className="detail-value">
              {systemAttributes?.business_domain ||
                systemAttributes?.domain ||
                attrs.business_domain ||
                "Not detected"}
            </span>
          </DetailRow>
        )}

        {/* Status field (system only) */}
        {nodeType === "system" && (
          <DetailRow
            label="Lifecycle Status"
            tooltip="Lifecycle stage: Active-Dev = new features being developed. Maintenance-Only = bugfixes only, no new features. Deprecated = scheduled for shutdown."
          >
            <span
              className={`detail-value${statusValue ? " status-badge" : ""}`}
            >
              {statusValue || "Unknown"}
            </span>
          </DetailRow>
        )}

        {/* Tier field (system only) */}
        {nodeType === "system" && (
          <DetailRow
            label="Criticality Tier"
            tooltip="Tier 1 = Production Critical (site-wide outage if down). Tier 2 = Standard (specific journey broken). Tier 3 = Internal/Development (minor impact)."
          >
            <span className="detail-value">{tierValue || "Unknown"}</span>
          </DetailRow>
        )}

        {/* Data class field (system only) */}
        {nodeType === "system" && (
          <DetailRow
            label="Data Sensitivity"
            tooltip="PII = names, emails, addresses. Credit-Card = Payment data. Legal/Security = Compliance, audit, encryption. General = Non-sensitive data."
          >
            <span className="detail-value">
              {dataClassValue || "Not classified"}
            </span>
          </DetailRow>
        )}

        {/* Active experts (system only) */}
        {nodeType === "system" && activeExpertsValue != null && (
          <DetailRow
            label="Active Experts (Bus Factor)"
            tooltip="Bus factor: contributors with 3+ commits in last 90 days. 0 = high risk (no active maintainers). 1 = single point of failure. Higher is better."
          >
            {(() => {
              const rawValue = activeExpertsValue;
              const isZero = rawValue === 0;
              const label =
                rawValue == null
                  ? "Unknown"
                  : rawValue === 0
                    ? "No active experts"
                    : rawValue === 1
                      ? "1 active expert"
                      : `${rawValue} active experts`;
              return (
                <span
                  className={`detail-value active-experts-value ${isZero ? "active-experts-zero" : ""}`}
                >
                  {label}
                </span>
              );
            })()}
          </DetailRow>
        )}

        {/* Documentation Quality (system only) */}
        {nodeType === "system" &&
          (docQuality.score != null || docQuality.tier) && (
          <DetailRow
            label="Documentation Quality"
            tooltip="Scored from: README depth, OpenAPI/Swagger, inline docs, ADRs, CHANGELOG, examples. EXCELLENT ≥75, ADEQUATE ≥45, POOR <45."
          >
            <span className="detail-value">
              {docQuality.tier && (
                <span style={{ marginRight: 6 }}>{docQuality.tier}</span>
              )}
              {docQuality.score != null && (
                <span style={{ color: "#64748b" }}>
                  ({docQuality.score}/100)
                </span>
              )}
            </span>
          </DetailRow>
        )}

        {/* Deployment Targets (system only) */}
        {nodeType === "system" && deploymentTargets.length > 0 && (
          <DetailRow
            label="Deployment Targets"
            tooltip="Where the service is deployed: Container, Kubernetes, Serverless, PaaS, VM, or Bare-Metal. Detected from Dockerfile, Helm charts, serverless.yml, etc."
          >
            <span className="detail-value">{deploymentTargets.join(", ")}</span>
          </DetailRow>
        )}

        {/* Compliance status (system only) */}
        {nodeType === "system" && (
          <DetailRow
            label="Architectural Compliance"
            tooltip="Calculated from: tier-data alignment, ownership, bus factor, and lifecycle. COMPLIANT = proper governance. AT_RISK = ownership/maintenance gaps. NON_COMPLIANT = sensitive data mishandled or abandoned."
          >
            <span
              className={`detail-value${complianceStatus && complianceStatus !== "UNKNOWN" ? " status-badge" : ""}`}
            >
              {complianceStatus && complianceStatus !== "UNKNOWN"
                ? complianceStatusLabel || complianceStatus
                : "Not assessed"}
            </span>
          </DetailRow>
        )}

        {/* Compliance confidence (system only) */}
        {nodeType === "system" &&
          complianceConfidencePercent !== undefined &&
          complianceStatus !== "UNKNOWN" && (
            <DetailRow
              label="Compliance Confidence"
              tooltip="Based on metadata completeness: higher when tier, data classification, and owner are known. Range 50-100%."
            >
              <span className="detail-value">
                {complianceConfidencePercent}%
              </span>
            </DetailRow>
          )}

        {/* Compliance factors (system only) */}
        {nodeType === "system" && complianceFactors.length > 0 && (
          <DetailRow
            label="Compliance Issues"
            tooltip="Detected architectural risks: sensitive data in low tiers, missing ownership, bus factor concerns, deprecated services with sensitive data, or single points of failure."
          >
            <FormattedDetailValue value={complianceFactors} />
          </DetailRow>
        )}

        {/* Git activity */}
        {nodeType === "system" && systemAttributes?.commit_count_90d != null && (
          <DetailRow
            label="Git Activity (90d)"
            tooltip="Number of commits in the last 90 days. Low activity on a Tier-1 system may indicate maintenance risk. Shows 'No git access' when the repository was extracted without a .git directory (e.g. from a ZIP download). Re-extract from a proper git clone to populate this field."
          >
            {systemAttributes?.commit_count_90d != null ? (
              <span className="detail-value">
                {systemAttributes.commit_count_90d} commits
                {systemAttributes?.commit_count_30d != null && (
                  <span style={{ color: "#64748b", marginLeft: 8 }}>
                    ({systemAttributes.commit_count_30d} in last 30d)
                  </span>
                )}
              </span>
            ) : (
              <span className="detail-value" style={{ color: "#94a3b8" }}>
                No git access — re-extract from a git clone
              </span>
            )}
          </DetailRow>
        )}

        {/* Last commit date */}
        {nodeType === "system" && systemAttributes?.last_commit_date && (
          <DetailRow label="Last Commit">
            <span className="detail-value">
              {systemAttributes.last_commit_date}
            </span>
          </DetailRow>
        )}

        {/* Container description (fallback when LLM description not loaded) */}
        {!nodeDescription &&
          nodeType === "container" &&
          (selectedNode?.containerMeta?.description || attrs.description) && (
            <div className="detail-row">
              <FormattedDetailValue
                value={
                  selectedNode?.containerMeta?.description || attrs.description
                }
                className="description-text"
                preserveWhitespace
              />
            </div>
          )}

        {/* Technology (container) */}
        {nodeType === "container" &&
          (selectedNode?.containerMeta?.technology || attrs.technology) && (
            <DetailRow
              label="Technology"
              tooltip="Primary technology stack: Python/FastAPI, React/TypeScript, PostgreSQL, Redis, etc."
              className="metadata-row"
            >
              <span className="detail-value">
                {selectedNode?.containerMeta?.technology || attrs.technology}
              </span>
            </DetailRow>
          )}

        {/* Container Type */}
        {nodeType === "container" &&
          (selectedNode?.containerMeta?.container_type ||
            attrs.container_type) && (
            <div className="detail-row metadata-row">
              <span className="detail-label">Container Type</span>
              <span className="detail-value">
                {selectedNode?.containerMeta?.container_type ||
                  attrs.container_type}
              </span>
            </div>
          )}

        {/* Protocol (container or external_system) */}
        {(nodeType === "container" ||
          isExternalDependencyNode ||
          nodeType === "external_system") &&
          (selectedNode?.containerMeta?.protocol || attrs.protocol) && (
            <div className="detail-row metadata-row">
              <span className="detail-label">Protocol</span>
              <span className="detail-value">
                {selectedNode?.containerMeta?.protocol || attrs.protocol}
              </span>
            </div>
          )}

        {/* Connections (container or component) */}
        {(nodeType === "container" || nodeType === "component") &&
          attrs.connections &&
          ((attrs.connections.outgoing?.length ?? 0) > 0 ||
            (attrs.connections.incoming?.length ?? 0) > 0) && (
            <DetailRow
              label="Connections"
              tooltip="Relationships this node participates in, derived from the architecture graph."
            >
              <div className="detail-value" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {(attrs.connections.outgoing || []).map(
                  (c: any, i: number) => (
                    <div key={`out-${i}`}>
                      <span style={{ color: "#10b981", marginRight: 6 }}>→</span>
                      <strong>{c.name}</strong>
                      {c.protocol ? ` (${c.protocol})` : ""}
                      {c.label ? ` — ${c.label}` : ""}
                      {c.description ? ` — ${c.description}` : ""}
                    </div>
                  ),
                )}
                {(attrs.connections.incoming || []).map(
                  (c: any, i: number) => (
                    <div key={`in-${i}`}>
                      <span style={{ color: "#6366f1", marginRight: 6 }}>←</span>
                      <strong>{c.name}</strong>
                      {c.protocol ? ` (${c.protocol})` : ""}
                      {c.label ? ` — ${c.label}` : ""}
                      {c.description ? ` — ${c.description}` : ""}
                    </div>
                  ),
                )}
              </div>
            </DetailRow>
          )}

        {/* Components Inside (container only) */}
        {nodeType === "container" &&
          Array.isArray(attrs.componentsInside) &&
          attrs.componentsInside.length > 0 && (
            <DetailRow
              label="Components Inside"
              tooltip="Components detected inside this container."
            >
              <FormattedDetailValue value={attrs.componentsInside} />
            </DetailRow>
          )}

        {/* Component Role (component only) */}
        {nodeType === "component" && attrs.component_type && (
          <DetailRow
            label="Component Role"
            tooltip="What role this component plays: http_handler, service_layer, database_adapter, model, etc."
            className="metadata-row"
          >
            <span className="detail-value">{attrs.component_type}</span>
          </DetailRow>
        )}

        {/* Endpoint (component only) */}
        {nodeType === "component" &&
          (attrs.endpoint_method || attrs.endpoint_path) && (
            <DetailRow
              label="Endpoint"
              tooltip="HTTP method and path served by this component."
              className="metadata-row"
            >
              <span className="detail-value">
                <code className="endpoint-path">
                  {[attrs.endpoint_method, attrs.endpoint_path]
                    .filter(Boolean)
                    .join(" ")}
                </code>
              </span>
            </DetailRow>
          )}

        {/* Language (component only) */}
        {nodeType === "component" && attrs.language && (
          <DetailRow
            label="Language"
            className="metadata-row"
          >
            <span className="detail-value">{attrs.language}</span>
          </DetailRow>
        )}

        {/* Container (component only) */}
        {nodeType === "component" && attrs.container && (
          <DetailRow
            label="Container"
            tooltip="The container this component lives in."
            className="metadata-row"
          >
            <span className="detail-value">{attrs.container}</span>
          </DetailRow>
        )}

        {/* Technology Stack (system-level languages + frameworks) */}
        {(systemAttributes?.languages?.length > 0 ||
          systemAttributes?.frameworks?.length > 0) && (
          <DetailRow
            label="Technology Stack"
            tooltip="Languages and frameworks detected across the service's source code and package manifests."
            className="metadata-row"
          >
            <span className="detail-value">
              {[
                ...(systemAttributes?.languages || []).map((l: any) =>
                  typeof l === "string" ? l : l?.language || l?.name || "",
                ),
                ...(systemAttributes?.frameworks || []).map((f: any) =>
                  typeof f === "string" ? f : f?.name || "",
                ),
              ]
                .filter(Boolean)
                .join(", ") || "—"}
            </span>
          </DetailRow>
        )}

        {/* External Dependencies (system node) */}
        {selectedNode?.type === "system" &&
          (systemAttributes?.external_dependencies?.length > 0 ||
            attrs.external_dependencies?.length > 0) && (
            <DetailRow
              label="External Dependencies"
              tooltip="Third-party services detected from package manifests: databases, message brokers, cloud services, etc."
            >
              <FormattedDetailValue
                value={(
                  systemAttributes?.external_dependencies ||
                  attrs.external_dependencies ||
                  []
                ).map((dependency: any) =>
                  typeof dependency === "string"
                    ? dependency
                    : `${dependency.name}${dependency.type ? ` (${dependency.type})` : ""}`,
                )}
              />
            </DetailRow>
          )}

        {/* File path */}
        {selectedNode?.file && (
          <DetailRow
            label="File"
            tooltip="Source file path where this component or container was detected. Relative to repository root."
            className="metadata-row"
          >
            <span className="detail-value file-path">{selectedNode.file}</span>
          </DetailRow>
        )}

        {chatMessages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`chat-message ${message.role}${message.streaming ? " streaming" : ""}`}
          >
            <div className="message-content">
              <FormattedDetailValue
                value={message.content}
                preserveWhitespace
              />
            </div>
          </div>
        ))}
        <div ref={chatEndRef} aria-hidden="true" />
      </div>

      {/* Chat Input */}
      <div className="chat-input-container">
        {chatStatus}
        <div className="chat-input-wrapper">
          <textarea
            placeholder="Ask about this node..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            className="send-btn"
            aria-label="Send chat message"
            onClick={handleSendChat}
            disabled={!chatInput.trim() || isChatLoading}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
