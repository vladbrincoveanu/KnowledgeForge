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

const decisionModeLabels: Record<string, string> = {
  deterministic: "Deterministic",
  llm_adjudicated: "LLM Adjudicated",
  human_reviewed: "Human Reviewed",
};

const reviewStatusLabels: Record<string, string> = {
  auto_accepted: "Auto Accepted",
  needs_review: "Needs Human Review",
  approved: "Approved",
  rejected: "Rejected",
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

function formatDecisionMode(mode?: string) {
  if (!mode) return "";
  return decisionModeLabels[mode] || mode.replace(/_/g, " ");
}

function formatReviewStatus(status?: string) {
  if (!status) return "";
  return reviewStatusLabels[status] || status.replace(/_/g, " ");
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
  onApplyReviewDecision?: (decision: {
    nodeId: string;
    value: string;
    label: string;
    description?: string;
  }) => void;
}

export default function NodeDetailsPanel({
  selectedNode,
  onClose,
  nodeDescription,
  isNodeLoading,
  chatMessages,
  isChatLoading,
  onSendChat,
  onApplyReviewDecision,
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

  const handlePromptSuggestionClick = async (prompt: string) => {
    if (isChatLoading) return;
    setChatInput("");
    await onSendChat(prompt);
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
  const reviewStatusLabel = formatReviewStatus(attrs.review_status);
  const decisionModeLabel = formatDecisionMode(attrs.decision_mode);
  const reviewThresholdPercent =
    attrs.review_threshold != null
      ? Math.round(Number(attrs.review_threshold) * 100)
      : undefined;
  const evidenceItems: string[] = Array.isArray(attrs.evidence)
    ? attrs.evidence
        .map((item: any) =>
          [item?.source, item?.snippet].filter(Boolean).join(" — "),
        )
        .filter((item: string) => Boolean(item))
    : [];
  const promptSuggestions: string[] = Array.isArray(attrs.suggested_prompts)
    ? attrs.suggested_prompts.filter(
        (item: unknown): item is string => typeof item === "string",
      )
    : [];
  const providerAlternatives: any[] = Array.isArray(attrs.provider_alternatives)
    ? attrs.provider_alternatives
    : [];
  const reviewOptions: any[] = Array.isArray(attrs.review_options)
    ? attrs.review_options
    : [];
  const selectedNodeLabel =
    selectedNode?.name ||
    selectedNode?.label ||
    selectedNode?.id ||
    "this dependency";
  const isExternalDependencyNode =
    String(nodeType || "").startsWith("external") || Boolean(attrs.is_external);
  const nodeTypeLabel = isExternalDependencyNode
    ? "External Dependency"
    : formatNodeTypeLabel(nodeType);
  const needsHumanReview =
    Boolean(attrs.requires_human_review) ||
    reviewStatusLabel === "Needs Human Review";
  const normalizedSelectedName = String(selectedNode?.name || "")
    .trim()
    .toLowerCase();
  const normalizedContextName = String(attrs.context_name || "")
    .trim()
    .toLowerCase();
  const normalizedRawName = String(attrs.raw_name || "")
    .trim()
    .toLowerCase();
  const showRawIntegrationLabel =
    Boolean(attrs.raw_name) &&
    normalizedRawName !== normalizedSelectedName &&
    normalizedRawName !== normalizedContextName;
  const showDetectedFrom =
    Boolean(attrs.detected_from) && attrs.detected_from !== selectedNode?.file;

  // Person/actor node — dedicated panel
  if (nodeType === "person") {
    const actorDesc = attrs.description || attrs.role || "";
    return (
      <aside className="node-details-panel chat-style">
        <div className="chat-header">
          <div className="chat-avatar">👤</div>
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
          <div className="chat-avatar">🔍</div>
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
        <div className={`chat-avatar node-type-${nodeType}`}>
          {nodeType === "system"
            ? "🏗️"
            : nodeType === "container"
              ? "📦"
              : nodeType === "component"
                ? "⚙️"
                : isExternalDependencyNode
                  ? "🌐"
                  : "📄"}
        </div>
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

        {/* Owner field */}
        {(systemAttributes ||
          attrs.owner != null ||
          attrs.owner_contributors != null ||
          containerMeta.owner ||
          containerMeta.owner_team) && (
          <DetailRow
            label="Owner Team"
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
              {systemAttributes.service_count} microservices
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

        {/* Status field */}
        {(nodeType === "system" || statusValue != null) && (
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

        {/* Tier field */}
        {(nodeType === "system" || tierValue != null) && (
          <DetailRow
            label="Criticality Tier"
            tooltip="Tier 1 = Production Critical (site-wide outage if down). Tier 2 = Standard (specific journey broken). Tier 3 = Internal/Development (minor impact)."
          >
            <span className="detail-value">{tierValue || "Unknown"}</span>
          </DetailRow>
        )}

        {/* Data class field */}
        {(nodeType === "system" || dataClassValue != null) && (
          <DetailRow
            label="Data Sensitivity"
            tooltip="PII = names, emails, addresses. Credit-Card = Payment data. Legal/Security = Compliance, audit, encryption. General = Non-sensitive data."
          >
            <span className="detail-value">
              {dataClassValue || "Not classified"}
            </span>
          </DetailRow>
        )}

        {/* Active experts */}
        {(nodeType === "system" || activeExpertsValue != null) && (
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

        {/* Documentation Quality */}
        {(docQuality.score != null || docQuality.tier) && (
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

        {/* Deployment Targets */}
        {deploymentTargets.length > 0 && (
          <DetailRow
            label="Deployment Targets"
            tooltip="Where the service is deployed: Container, Kubernetes, Serverless, PaaS, VM, or Bare-Metal. Detected from Dockerfile, Helm charts, serverless.yml, etc."
          >
            <span className="detail-value">{deploymentTargets.join(", ")}</span>
          </DetailRow>
        )}

        {/* Compliance status */}
        {(nodeType === "system" || complianceStatus) && (
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

        {/* Compliance confidence */}
        {(nodeType === "system" || complianceStatus) &&
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

        {/* Compliance factors */}
        {complianceFactors.length > 0 && (
          <DetailRow
            label="Compliance Issues"
            tooltip="Detected architectural risks: sensitive data in low tiers, missing ownership, bus factor concerns, deprecated services with sensitive data, or single points of failure."
          >
            <FormattedDetailValue value={complianceFactors} />
          </DetailRow>
        )}

        {/* Git activity */}
        {nodeType === "system" && (
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

        {/* Node type metadata */}
        {selectedNode?.type && !isExternalDependencyNode && (
          <DetailRow
            label="Type"
            tooltip="Node type: system (entire service), container (API/UI/DB), component (class/module), or external_system (third-party service)."
            className="metadata-row"
          >
            <span className="detail-value">
              {formatNodeTypeLabel(selectedNode.type)}
            </span>
          </DetailRow>
        )}

        {/* Technology (container) */}
        {selectedNode?.containerMeta?.technology && (
          <DetailRow
            label="Technology"
            tooltip="Primary technology stack: Python/FastAPI, React/TypeScript, PostgreSQL, Redis, etc. Detected from code and dependencies."
            className="metadata-row"
          >
            <span className="detail-value">
              {selectedNode.containerMeta.technology}
            </span>
          </DetailRow>
        )}

        {/* Container Type */}
        {(selectedNode?.containerMeta?.container_type ||
          attrs.container_type) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Container Type</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.container_type ||
                attrs.container_type}
            </span>
          </div>
        )}

        {/* Runtime version */}
        {(selectedNode?.containerMeta?.runtime_info ||
          attrs.runtime_info ||
          selectedNode?.containerMeta?.runtime_environment ||
          attrs.runtime_environment) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Runtime</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.runtime_info ||
                attrs.runtime_info ||
                selectedNode?.containerMeta?.runtime_environment ||
                attrs.runtime_environment}
            </span>
          </div>
        )}

        {/* Protocol */}
        {(selectedNode?.containerMeta?.protocol || attrs.protocol) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Protocol</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.protocol || attrs.protocol}
            </span>
          </div>
        )}

        {/* Deployment mechanism */}
        {(selectedNode?.containerMeta?.deployment || attrs.deployment) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Deployment</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.deployment || attrs.deployment}
            </span>
          </div>
        )}

        {/* Health Endpoint */}
        {(selectedNode?.containerMeta?.health_endpoint ||
          attrs.health_endpoint) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Health Endpoint</span>
            <span className="detail-value">
              <code className="endpoint-path">
                {selectedNode?.containerMeta?.health_endpoint ||
                  attrs.health_endpoint}
              </code>
            </span>
          </div>
        )}

        {/* Container description */}
        {!nodeDescription &&
          (selectedNode?.containerMeta?.description || attrs.description) &&
          selectedNode?.type !== "system" && (
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
                ...(systemAttributes?.languages || []),
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

        {/* Repository URL */}
        {(systemAttributes?.repository_url || attrs.repository_url) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Repository</span>
            <span className="detail-value">
              <a
                href={systemAttributes?.repository_url || attrs.repository_url}
                target="_blank"
                rel="noopener noreferrer"
                className="external-link"
              >
                {systemAttributes?.repository_url || attrs.repository_url}
              </a>
            </span>
          </div>
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

        {/* External service URL */}
        {attrs.url && (
          <DetailRow
            label="Service URL"
            tooltip="External service URL or API endpoint for third-party integrations."
          >
            <span className="detail-value">
              <a
                href={attrs.url}
                target="_blank"
                rel="noopener noreferrer"
                className="external-link"
              >
                {attrs.url}
              </a>
            </span>
          </DetailRow>
        )}

        {showRawIntegrationLabel && (
          <DetailRow
            label="Integration Surface"
            tooltip="Technical integration label detected in code or config. Context level should prefer the business-facing company/system name."
          >
            <span className="detail-value">{attrs.raw_name}</span>
          </DetailRow>
        )}

        {attrs.integration_surface && (
          <DetailRow
            label="Technical Surface"
            tooltip="Protocol, SDK, or interface detail stripped from the context-level business name."
          >
            <span className="detail-value">{attrs.integration_surface}</span>
          </DetailRow>
        )}

        {(attrs.company || attrs.provider) && (
          <DetailRow
            label="Company"
            tooltip="Resolved provider or company behind this external dependency."
          >
            <span className="detail-value">
              {attrs.company || attrs.provider}
            </span>
          </DetailRow>
        )}

        {/* Access endpoint */}
        {(selectedNode?.containerMeta?.endpoint ||
          attrs.endpoint ||
          attrs.access_path) && (
          <DetailRow
            label="Access Endpoint"
            tooltip="The URL path or endpoint used to access this service or UI directly."
          >
            <span className="detail-value">
              <code className="endpoint-path">
                {selectedNode?.containerMeta?.endpoint ||
                  attrs.endpoint ||
                  attrs.access_path}
              </code>
            </span>
          </DetailRow>
        )}

        {/* Detected from */}
        {showDetectedFrom && (
          <DetailRow
            label="Detected From"
            tooltip="Configuration file where this dependency was found: package.json, requirements.txt, docker-compose.yml, Helm charts, etc."
            className="metadata-row"
          >
            <span className="detail-value">{attrs.detected_from}</span>
          </DetailRow>
        )}

        {decisionModeLabel && (
          <DetailRow
            label="Decision Mode"
            tooltip="How this dependency classification was produced: rule-based, LLM-adjudicated, or human-reviewed."
          >
            <span className="detail-value">{decisionModeLabel}</span>
          </DetailRow>
        )}

        {reviewStatusLabel && (
          <DetailRow
            label="Review Status"
            tooltip="Whether this dependency was auto-accepted or still requires a human decision."
          >
            <span className="detail-value">{reviewStatusLabel}</span>
          </DetailRow>
        )}

        {/* C4 Classification — only show when known (not UNKNOWN) */}
        {attrs.dependency_type && attrs.dependency_type !== "UNKNOWN" && (
          <DetailRow
            label="C4 Classification"
            tooltip="BUSINESS_SYSTEM = External business service (should appear at Context level). TECHNICAL_INFRA = Infrastructure component (should appear at Container level). Classified by type inference or LLM."
          >
            <span
              className={`detail-value pill ${
                attrs.dependency_type === "BUSINESS_SYSTEM"
                  ? "business-system-pill"
                  : "technical-infra-pill"
              }`}
            >
              {attrs.dependency_type}
            </span>
          </DetailRow>
        )}

        {/* Classification confidence — only show when known */}
        {attrs.dependency_type &&
          attrs.dependency_type !== "UNKNOWN" &&
          attrs.classification_confidence !== undefined && (
            <DetailRow
              label="Classification Confidence"
              tooltip="How confident the classifier is about this categorization. Range: 0.0-1.0. Higher is better."
            >
              <span className="detail-value">
                {Math.round(attrs.classification_confidence * 100)}%
              </span>
            </DetailRow>
          )}

        {attrs.requires_human_review &&
          reviewThresholdPercent !== undefined && (
            <DetailRow
              label="Human Review Threshold"
              tooltip="Threshold below which the classifier requires manual confirmation before the dependency is trusted."
            >
              <span className="detail-value">{reviewThresholdPercent}%</span>
            </DetailRow>
          )}

        {/* Classification reasoning */}
        {attrs.classification_reasoning &&
          (attrs.dependency_type !== "UNKNOWN" ||
            attrs.requires_human_review) && (
            <DetailRow
              label="Classification Reasoning"
              tooltip="Explanation of why this dependency was classified as business or technical."
            >
              <FormattedDetailValue
                value={attrs.classification_reasoning}
                preserveWhitespace
              />
            </DetailRow>
          )}

        {attrs.human_review_summary && (
          <DetailRow
            label="Human Review Outcome"
            tooltip="Latest manual decision captured from the reviewer in this session."
          >
            <FormattedDetailValue
              value={attrs.human_review_summary}
              preserveWhitespace
            />
          </DetailRow>
        )}

        {evidenceItems.length > 0 && (
          <DetailRow
            label="Evidence"
            tooltip="Supporting traces used to derive this external dependency."
          >
            <FormattedDetailValue value={evidenceItems} />
          </DetailRow>
        )}

        {needsHumanReview && reviewOptions.length > 0 && (
          <div className="chat-message assistant review-message">
            <div className="message-content assistant-workbench">
              <p className="assistant-callout-title">
                I am not fully confident where {selectedNodeLabel} belongs in
                the context diagram.
              </p>
              <p>
                Tell me what you think by clicking one option below. I will mark
                the dependency as human reviewed for this session.
              </p>
              <div className="review-option-grid">
                {reviewOptions.map((option: any) => (
                  <button
                    key={`${selectedNode?.id}-${option.id || option.value}`}
                    type="button"
                    className="review-option-btn"
                    onClick={() =>
                      onApplyReviewDecision?.({
                        nodeId: selectedNode?.id,
                        value: option.value,
                        label: option.label,
                        description: option.description,
                      })
                    }
                  >
                    <span className="review-option-label">{option.label}</span>
                    {option.description && (
                      <span className="review-option-description">
                        {option.description}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              {reviewThresholdPercent !== undefined && (
                <div className="assistant-workbench-footnote">
                  Review threshold: {reviewThresholdPercent}% confidence.
                </div>
              )}
            </div>
          </div>
        )}

        {(providerAlternatives.length > 0 || promptSuggestions.length > 0) && (
          <div className="chat-message assistant">
            <div className="message-content assistant-workbench">
              <p className="assistant-callout-title">
                {providerAlternatives.length > 0
                  ? `Possible alternatives for ${selectedNodeLabel}`
                  : `Ask the model for a recommendation about ${selectedNodeLabel}`}
              </p>
              {providerAlternatives.length > 0 && (
                <p>
                  These are business-facing provider choices you may want to
                  compare before keeping the dependency in the architecture.
                </p>
              )}
              {providerAlternatives.length > 0 && (
                <div className="provider-alternative-list">
                  {providerAlternatives.map((alternative: any) => (
                    <div
                      key={`${selectedNode?.id}-${alternative.provider}`}
                      className="provider-alternative-card"
                    >
                      <div className="provider-alternative-header">
                        <span className="provider-alternative-name">
                          {alternative.provider}
                        </span>
                        {(alternative.price_tier ||
                          alternative.performance_tier) && (
                          <span className="provider-alternative-meta">
                            {[
                              alternative.price_tier,
                              alternative.performance_tier,
                            ]
                              .filter(Boolean)
                              .join(" / ")}
                          </span>
                        )}
                      </div>
                      {(alternative.profile || alternative.notes) && (
                        <div className="provider-alternative-description">
                          {alternative.profile || alternative.notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {promptSuggestions.length > 0 && (
                <div className="prompt-chip-row">
                  {promptSuggestions.map((prompt) => (
                    <button
                      key={`${selectedNode?.id}-${prompt}`}
                      type="button"
                      className="prompt-chip"
                      onClick={() => void handlePromptSuggestionClick(prompt)}
                      disabled={isChatLoading}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
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
