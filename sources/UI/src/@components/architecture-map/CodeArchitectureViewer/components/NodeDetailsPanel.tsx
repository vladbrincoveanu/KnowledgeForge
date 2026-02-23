import React, { useState } from 'react';

// ── Compliance helpers ────────────────────────────────────────────────────────

const complianceStatusLabels: Record<string, string> = {
  EXCELLENT: 'Excellent',
  COMPLIANT: 'Compliant',
  AT_RISK: 'At risk',
  NON_COMPLIANT: 'Non-compliant',
  UNKNOWN: 'Unknown',
};

const complianceFactorLabels: Record<string, string> = {
  sensitive_data_low_tier: 'Sensitive data in a low-tier system',
  sensitive_data_no_owner: 'Sensitive data without an owner',
  critical_service_no_owner: 'Critical service without an owner',
  no_active_maintainers: 'No active maintainers',
  deprecated_with_sensitive_data: 'Deprecated service with sensitive data',
  single_point_of_failure: 'Single maintainer for a Tier 1 service',
};

function formatComplianceStatus(status?: string) {
  if (!status) return "";
  return complianceStatusLabels[status] || status.replace(/_/g, " ");
}

function formatComplianceFactor(factor: string) {
  const cleaned = factor.trim();
  return complianceFactorLabels[cleaned] || cleaned.replace(/_/g, " ");
}

function formatComplianceFactors(factors?: string[]): string[] {
  return (factors || []).map(formatComplianceFactor).filter(Boolean);
}

function formatDocQuality(dq: any): { score: number | null; tier: string | null } {
  if (!dq) return { score: null, tier: null };
  if (typeof dq === "object") return { score: dq.score ?? dq.total_score ?? null, tier: dq.tier ?? dq.quality_tier ?? null };
  if (typeof dq === "number") return { score: dq, tier: null };
  return { score: null, tier: String(dq) };
}

const TECH_DEP_TYPES = new Set([
  "messaging","cache","database","storage","logging","monitoring",
  "observability","search","rpc","error-tracking","authentication",
  "service-discovery","sms","email","payment",
]);

// ── Small sub-components ──────────────────────────────────────────────────────

function GridCell({ label, value, wide }: { label: string; value: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`ndp-grid-cell${wide ? " ndp-grid-cell--wide" : ""}`}>
      <span className="ndp-grid-label">{label}</span>
      <span className="ndp-grid-value">{value || <span className="ndp-empty">—</span>}</span>
    </div>
  );
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="ndp-section">
      <button className="ndp-section-toggle" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <span className={`ndp-section-chevron${open ? " open" : ""}`}>›</span>
      </button>
      {open && <div className="ndp-section-body">{children}</div>}
    </div>
  );
}

function PropRow({ label, value, tooltip }: { label: string; value: React.ReactNode; tooltip?: string }) {
  return (
    <div className="ndp-prop-row">
      <span className="ndp-prop-label">
        {label}
        {tooltip && <span className="ndp-tooltip-hint" title={tooltip}>ⓘ</span>}
      </span>
      <span className="ndp-prop-value">{value}</span>
    </div>
  );
}

// ── Main props ────────────────────────────────────────────────────────────────

interface NodeDetailsPanelProps {
  selectedNode: any;
  onClose: () => void;
  nodeDescription: string;
  isNodeLoading: boolean;
  variant?: "side" | "bottom" | "overlay";
  showClose?: boolean;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function NodeDetailsPanel({
  selectedNode,
  onClose,
  nodeDescription,
  isNodeLoading,
  variant = "side",
  showClose = true,
}: NodeDetailsPanelProps) {
  const nodeType = selectedNode?.type || "";
  const attrs = selectedNode?.attributes || {};
  const sysAttrs = nodeType === "system" ? attrs : null;
  const cMeta = selectedNode?.containerMeta || {};

  const name = selectedNode?.name || selectedNode?.label || selectedNode?.id || "Node";
  const desc = nodeDescription || sysAttrs?.purpose || sysAttrs?.description || attrs.description || cMeta.description || "";

  const owner = sysAttrs?.owner_team || sysAttrs?.owner || cMeta.owner || attrs.owner;
  const status = sysAttrs?.status || attrs.status;
  const tier = sysAttrs?.criticality || sysAttrs?.tier || attrs.tier;
  const domain = sysAttrs?.business_domain || sysAttrs?.domain || attrs.business_domain;
  const dataClass = sysAttrs?.data_class || attrs.data_class;
  const dataSteward = sysAttrs?.data_steward || attrs.data_steward;
  const squad = sysAttrs?.squad || attrs.squad;
  const sensitivityTags: string[] = sysAttrs?.sensitivity_tags || attrs.sensitivity_tags || [];
  const qualityScore = sysAttrs?.quality_score ?? attrs.quality_score;
  const usageStats = sysAttrs?.usage_stats || attrs.usage_stats;
  const columnLineageSummary = sysAttrs?.column_lineage_summary || attrs.column_lineage_summary;
  const rawExperts = sysAttrs?.active_experts ?? attrs.active_experts;
  const busFactor = rawExperts == null ? null : rawExperts === 0 ? "None" : String(rawExperts);

  const complianceStatus = sysAttrs?.compliance ?? attrs.compliance;
  const complianceLabel = formatComplianceStatus(complianceStatus);
  const complianceFactors = formatComplianceFactors(sysAttrs?.compliance_factors ?? attrs.compliance_factors);
  const complianceConfidence = sysAttrs?.compliance_confidence ?? attrs.compliance_confidence;
  const docQuality = formatDocQuality(sysAttrs?.documentation_quality);
  const deploymentTargets: string[] = sysAttrs?.deployment_targets || [];

  const allExternalDeps: any[] = sysAttrs?.external_dependencies || attrs.external_dependencies || [];
  const contextDeps = allExternalDeps.filter((d: any) => {
    const n = typeof d === "string" ? d : d?.name || "";
    if (!n || n.startsWith("*") || n.startsWith("$")) return false;
    const dt = d?.dependency_type;
    if (dt === "BUSINESS_SYSTEM") return true;
    if (dt === "TECHNICAL_INFRA") return false;
    return !TECH_DEP_TYPES.has(d?.type || "");
  });

  const isOverlay = variant === "overlay";
  const panelClass = `node-details-panel${isOverlay ? " ndp-overlay" : variant === "bottom" ? " bottom" : ""}`;

  const complianceColor =
    complianceStatus === "NON_COMPLIANT" ? "red" :
    complianceStatus === "AT_RISK" ? "amber" :
    complianceStatus === "COMPLIANT" || complianceStatus === "EXCELLENT" ? "green" : null;

  const typeColorClass =
    nodeType === "system" ? "ndp-type-system" :
    nodeType === "person" ? "ndp-type-person" :
    nodeType === "container" ? "ndp-type-container" :
    "ndp-type-external";

  // ── Person node ───────────────────────────────────────────────────────────
  if (nodeType === "person") {
    return (
      <aside className={panelClass}>
        <div className="ndp-header">
          <div className="ndp-header-left">
            <span className={`ndp-type-badge ${typeColorClass}`}>person</span>
            <span className="ndp-name">{name}</span>
          </div>
          {showClose && <button className="ndp-close" onClick={onClose}>✕</button>}
        </div>
        <div className="ndp-body">
          {(desc || isNodeLoading) && (
            <p className="ndp-desc">{isNodeLoading ? "Loading…" : desc}</p>
          )}
          <div className="ndp-grid">
            <GridCell label="Type" value="Actor / Person" wide />
            {attrs.role && <GridCell label="Role" value={attrs.role} wide />}
          </div>
        </div>
      </aside>
    );
  }

  // ── Generic / system / external node ─────────────────────────────────────
  return (
    <aside className={panelClass}>

      {/* Header */}
      <div className="ndp-header">
        <div className="ndp-header-left">
          <span className={`ndp-type-badge ${typeColorClass}`}>{nodeType || "node"}</span>
          <span className="ndp-name" title={name}>{name}</span>
        </div>
        {showClose && <button className="ndp-close" onClick={onClose}>✕</button>}
      </div>

      {/* Body */}
      <div className="ndp-body">

        {/* Description */}
        {(desc || isNodeLoading) && (
          <p className="ndp-desc">{isNodeLoading ? "Loading description…" : desc}</p>
        )}

        {/* Key metrics grid — system nodes */}
        {nodeType === "system" && (
          <div className="ndp-grid">
            <GridCell label="Owner" value={owner || <span className="ndp-empty">Unassigned</span>} />
            <GridCell label="Data Steward" value={dataSteward || <span className="ndp-empty">Unassigned</span>} />
            <GridCell label="Status" value={status} />
            <GridCell label="Criticality" value={tier} />
            <GridCell label="Bus Factor" value={rawExperts === 0 ? <span className="ndp-warn">⚠ None</span> : busFactor} />
            <GridCell label="Business Domain" value={domain} />
            <GridCell label="Data Sensitivity" value={dataClass} />
            <GridCell label="Squad" value={squad} />
            <GridCell label="Quality Score" value={qualityScore != null ? `${qualityScore}/100` : <span className="ndp-empty">—</span>} />
          </div>
        )}

        {/* Compliance banner */}
        {complianceColor && (
          <div className={`ndp-compliance ndp-compliance--${complianceColor}`}>
            <span className="ndp-compliance-title">
              {complianceColor === "green" ? "✓" : "⚠"} {complianceLabel}
              {complianceConfidence != null && (
                <span className="ndp-compliance-conf">{Math.round(100 * complianceConfidence)}% confidence</span>
              )}
            </span>
            {complianceFactors.length > 0 && (
              <ul className="ndp-compliance-factors">
                {complianceFactors.map(f => <li key={f}>{f}</li>)}
              </ul>
            )}
          </div>
        )}

        {/* System details section */}
        {nodeType === "system" && (
          <Section title="System Details">
            {(sysAttrs?.service_count ?? 0) > 0 && (
              <PropRow label="Services" value={`${sysAttrs.service_count} microservices`} tooltip="Total deployable containers/microservices." />
            )}
            {(docQuality.score != null || docQuality.tier) && (
              <PropRow
                label="Doc Quality"
                value={[docQuality.tier, docQuality.score != null ? `${docQuality.score}/100` : null].filter(Boolean).join(" · ")}
                tooltip="Scored from README, OpenAPI, inline docs, ADRs, CHANGELOG."
              />
            )}
            {sensitivityTags.length > 0 && (
              <PropRow label="Sensitivity Tags" value={sensitivityTags.join(", ")} tooltip="Normalized tags used in executive view and governance reporting." />
            )}
            {usageStats && (
              <PropRow
                label="Usage"
                value={[
                  usageStats.access_count != null ? `${usageStats.access_count} accesses` : null,
                  usageStats.percentile_bucket || null,
                  usageStats.window_days != null ? `${usageStats.window_days}d window` : null,
                ].filter(Boolean).join(" · ") || "Not configured"}
                tooltip="Access-frequency overlay input for optimization prioritization."
              />
            )}
            {columnLineageSummary && (
              <PropRow
                label="Column Lineage"
                value={columnLineageSummary.total_links != null ? `${columnLineageSummary.total_links} links` : "Not configured"}
                tooltip="Column-level lineage coverage summary."
              />
            )}
            {deploymentTargets.length > 0 && (
              <PropRow label="Deployment" value={deploymentTargets.join(", ")} tooltip="Detected from Dockerfile, Helm, serverless.yml, etc." />
            )}
            {((sysAttrs?.languages?.length > 0) || (sysAttrs?.frameworks?.length > 0)) && (
              <PropRow
                label="Tech Stack"
                value={[
                  ...(sysAttrs?.languages || []).map((l: any) => typeof l === "string" ? l : l?.name || ""),
                  ...(sysAttrs?.frameworks || []).map((f: any) => typeof f === "string" ? f : f?.name || ""),
                ].filter(Boolean).join(", ")}
                tooltip="Languages and frameworks from source and package manifests."
              />
            )}
            <PropRow
              label="Actors"
              value={(sysAttrs?.actors || []).length > 0
                ? (sysAttrs.actors as any[]).map((a: any) => a.name || a).join(", ")
                : "Not detected"}
              tooltip="Human users or systems directly interacting with this system."
            />
            {sysAttrs?.commit_count_90d != null ? (
              <PropRow
                label="Git Activity"
                value={`${sysAttrs.commit_count_90d} commits (90d)${sysAttrs?.commit_count_30d != null ? ` · ${sysAttrs.commit_count_30d} in 30d` : ""}`}
              />
            ) : (
              <PropRow label="Git Activity" value={<span style={{color:"#94a3b8"}}>No git access — re-extract from git clone</span>} />
            )}
            {sysAttrs?.last_commit_date && <PropRow label="Last Commit" value={sysAttrs.last_commit_date} />}
          </Section>
        )}

        {/* External dependencies */}
        {nodeType === "system" && contextDeps.length > 0 && (
          <Section title={`Dependencies (${contextDeps.length})`} defaultOpen={false}>
            <div className="ndp-chip-list">
              {contextDeps.map((d: any, i: number) => (
                <span key={i} className="ndp-chip">{typeof d === "string" ? d : d.name}</span>
              ))}
            </div>
          </Section>
        )}

        {/* Container / component metadata */}
        {nodeType !== "system" && (cMeta.technology || attrs.protocol || cMeta.container_type || attrs.container_type) && (
          <Section title="Technical Details">
            {cMeta.technology && <PropRow label="Technology" value={cMeta.technology} />}
            {(cMeta.container_type || attrs.container_type) && <PropRow label="Container Type" value={cMeta.container_type || attrs.container_type} />}
            {(cMeta.runtime_info || attrs.runtime_info) && <PropRow label="Runtime" value={cMeta.runtime_info || attrs.runtime_info} />}
            {(cMeta.protocol || attrs.protocol) && <PropRow label="Protocol" value={cMeta.protocol || attrs.protocol} />}
            {(cMeta.deployment || attrs.deployment) && <PropRow label="Deployment" value={cMeta.deployment || attrs.deployment} />}
            {(cMeta.health_endpoint || attrs.health_endpoint) && (
              <PropRow label="Health" value={<code className="ndp-code">{cMeta.health_endpoint || attrs.health_endpoint}</code>} />
            )}
            {(cMeta.endpoint || attrs.endpoint || attrs.access_path) && (
              <PropRow label="Endpoint" value={<code className="ndp-code">{cMeta.endpoint || attrs.endpoint || attrs.access_path}</code>} />
            )}
          </Section>
        )}

        {/* Classification (external nodes) */}
        {attrs.dependency_type && attrs.dependency_type !== "UNKNOWN" && (
          <Section title="Classification" defaultOpen={false}>
            <PropRow label="C4 Class" value={attrs.dependency_type} tooltip="BUSINESS_SYSTEM or TECHNICAL_INFRA." />
            {attrs.classification_confidence !== undefined && (
              <PropRow label="Confidence" value={`${Math.round(attrs.classification_confidence * 100)}%`} />
            )}
            {attrs.classification_reasoning && (
              <PropRow label="Reasoning" value={attrs.classification_reasoning} />
            )}
          </Section>
        )}

        {/* Repository & source */}
        {(attrs.repository_url || sysAttrs?.repository_url || selectedNode?.file || attrs.url) && (
          <Section title="Repository" defaultOpen={false}>
            {(sysAttrs?.repository_url || attrs.repository_url) && (
              <PropRow label="URL" value={
                <a href={sysAttrs?.repository_url || attrs.repository_url} target="_blank" rel="noopener noreferrer" className="ndp-link">
                  {(sysAttrs?.repository_url || attrs.repository_url).replace(/^https?:\/\//, "")}
                </a>
              } />
            )}
            {attrs.url && (
              <PropRow label="Service URL" value={<a href={attrs.url} target="_blank" rel="noopener noreferrer" className="ndp-link">{attrs.url}</a>} />
            )}
            {selectedNode?.file && (
              <PropRow label="File" value={<code className="ndp-code ndp-code--path">{selectedNode.file}</code>} />
            )}
          </Section>
        )}

        {/* Contributors */}
        {((sysAttrs?.owner_contributors || attrs.owner_contributors) ?? []).length > 0 && (
          <Section title="Contributors" defaultOpen={false}>
            <div className="ndp-chip-list">
              {(sysAttrs?.owner_contributors || attrs.owner_contributors || []).slice(0, 8).map((c: string, i: number) => (
                <span key={i} className="ndp-chip">{c}</span>
              ))}
            </div>
          </Section>
        )}

      </div>
    </aside>
  );
}
