import React from 'react';

// ── Compliance formatting helpers ─────────────────────────────────────────────

const complianceStatusLabels: Record<string, string> = {
  EXCELLENT: 'Excellent',
  COMPLIANT: 'Compliant',
  AT_RISK: 'At risk',
  NON_COMPLIANT: 'Non-compliant',
  UNKNOWN: 'Unknown',
};

const complianceFactorLabels: Record<string, string> = {
  sensitive_data_low_tier: 'Sensitive data stored in a low-tier system',
  sensitive_data_no_owner: 'Sensitive data without an owner',
  critical_service_no_owner: 'Critical service without an owner',
  no_active_maintainers: 'No active maintainers',
  deprecated_with_sensitive_data: 'Deprecated service with sensitive data',
  single_point_of_failure: 'Single maintainer for a Tier 1 service',
};

function formatComplianceStatus(status?: string) {
  if (!status) return '';
  return complianceStatusLabels[status] || status.replace(/_/g, ' ');
}

function formatComplianceFactor(factor: string) {
  const cleaned = factor.trim();
  const label = complianceFactorLabels[cleaned];
  if (label) return label;
  const spaced = cleaned.replace(/_/g, ' ');
  return spaced ? `${spaced[0].toUpperCase()}${spaced.slice(1)}` : '';
}

function formatComplianceFactors(factors?: string[]): string[] {
  return (factors || [])
    .map(formatComplianceFactor)
    .filter((v): v is string => Boolean(v));
}

function formatDocQuality(dq: any): { score: number | null; tier: string | null } {
  if (!dq) return { score: null, tier: null };
  if (typeof dq === 'object') {
    return {
      score: dq.score ?? dq.total_score ?? null,
      tier: dq.tier ?? dq.quality_tier ?? null,
    };
  }
  if (typeof dq === 'number') return { score: dq, tier: null };
  return { score: null, tier: String(dq) };
}

// ── Row helpers ───────────────────────────────────────────────────────────────

interface RowProps {
  label: string;
  tooltip?: string;
  children: React.ReactNode;
  className?: string;
}

function DetailRow({ label, tooltip, children, className = '' }: RowProps) {
  return (
    <div className={`detail-row ${className}`}>
      <span className="detail-label">
        {label}
        {tooltip && (
          <span className="tooltip-hint">
            ⓘ<span className="tooltip-content">{tooltip}</span>
          </span>
        )}
      </span>
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
}

export default function NodeDetailsPanel({
  selectedNode,
  onClose,
  nodeDescription,
  isNodeLoading,
}: NodeDetailsPanelProps) {
  const nodeType = selectedNode?.type;
  const attrs = selectedNode?.attributes || {};
  const systemAttributes = nodeType === 'system' ? attrs : null;

  const complianceStatus = systemAttributes?.compliance ?? attrs.compliance;
  const complianceStatusLabel = formatComplianceStatus(complianceStatus);
  const complianceConfidence = systemAttributes?.compliance_confidence ?? attrs.compliance_confidence;
  const complianceConfidencePercent =
    complianceConfidence != null ? Math.round(100 * complianceConfidence) : undefined;
  const complianceFactors = formatComplianceFactors(
    systemAttributes?.compliance_factors ?? attrs.compliance_factors
  );

  const docQuality = formatDocQuality(systemAttributes?.documentation_quality);
  const deploymentTargets: string[] = systemAttributes?.deployment_targets || [];

  // Person/actor node — dedicated panel
  if (nodeType === 'person') {
    const actorDesc = attrs.description || attrs.role || '';
    return (
      <aside className="node-details-panel">
        <div className="panel-header">
          <h3>
            <span style={{ marginRight: 6 }}>👤</span>
            {selectedNode?.name || selectedNode?.label || 'Actor'}
          </h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="panel-content">
          {(nodeDescription || isNodeLoading) && (
            <div className="detail-row description-row">
              <span className="detail-value description-text">
                {isNodeLoading ? 'Loading description…' : nodeDescription}
              </span>
            </div>
          )}
          {actorDesc && !nodeDescription && !isNodeLoading && (
            <div className="detail-row description-row">
              <span className="detail-value description-text">{actorDesc}</span>
            </div>
          )}
          <DetailRow label="Type" tooltip="C4 actor type: person (human user) or system (automated actor).">
            <span className="detail-value">Actor / Person</span>
          </DetailRow>
          {attrs.role && (
            <DetailRow label="Role">
              <span className="detail-value">{attrs.role}</span>
            </DetailRow>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="node-details-panel">
      <div className="panel-header">
        <h3>{selectedNode?.name || selectedNode?.label || selectedNode?.id || 'Node Details'}</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      <div className="panel-content">

        {/* Description */}
        {(nodeDescription || isNodeLoading) && (
          <div className="detail-row description-row">
            <span className="detail-value description-text">
              {isNodeLoading ? 'Loading description…' : nodeDescription}
            </span>
          </div>
        )}

        {/* Purpose/description (when no LLM description yet) */}
        {!nodeDescription && !isNodeLoading &&
          (systemAttributes?.purpose || systemAttributes?.description ||
           attrs.description) && (
          <div className="detail-row description-row">
            <span className="detail-value description-text">
              {systemAttributes?.purpose || systemAttributes?.description || attrs.description}
            </span>
          </div>
        )}

        {/* Owner field */}
        {(systemAttributes ||
          attrs.owner != null ||
          attrs.owner_contributors != null ||
          selectedNode?.containerMeta?.owner) && (
          <DetailRow
            label="Owner Team"
            tooltip="The team or individual responsible for this system. If unassigned, add a CODEOWNERS file or specify the team in the README."
          >
            <span className="detail-value">
              {systemAttributes?.owner_team ||
                systemAttributes?.owner ||
                selectedNode?.containerMeta?.owner ||
                attrs.owner ||
                'Unassigned'}
            </span>
            {((systemAttributes?.owner_contributors || attrs.owner_contributors) ?? []).length > 0 && (
              <div className="detail-sub">
                Contributors:{' '}
                {(systemAttributes?.owner_contributors || attrs.owner_contributors || [])
                  .slice(0, 3)
                  .join(', ')}
                {(systemAttributes?.owner_contributors || attrs.owner_contributors || []).length > 3 && '…'}
              </div>
            )}
          </DetailRow>
        )}

        {/* Actors list (system node) */}
        {nodeType === 'system' && (
          <DetailRow
            label="Actors"
            tooltip="Human users or external systems that directly interact with this system."
          >
            <span className="detail-value">
              {(systemAttributes?.actors || []).length > 0
                ? (systemAttributes?.actors || [])
                    .map((a: any) => `${a.name}${a.description ? ` — ${a.description}` : ''}`)
                    .join('; ')
                : 'Not detected'}
            </span>
          </DetailRow>
        )}

        {/* Service count */}
        {nodeType === 'system' && systemAttributes?.service_count > 0 && (
          <DetailRow
            label="Services"
            tooltip="Total number of deployable containers/microservices detected in this system."
          >
            <span className="detail-value">{systemAttributes.service_count} microservices</span>
          </DetailRow>
        )}

        {/* Business Domain */}
        {nodeType === 'system' && (
          <DetailRow
            label="Business Domain"
            tooltip="The business domain this system belongs to (e.g. Commerce, Identity, Logistics). Detected from service name, README, and package manifests."
          >
            <span className="detail-value">
              {systemAttributes?.business_domain || systemAttributes?.domain || attrs.business_domain || 'Not detected'}
            </span>
          </DetailRow>
        )}

        {/* Status field */}
        {nodeType === 'system' && (
          <DetailRow
            label="Lifecycle Status"
            tooltip="Lifecycle stage: Active-Dev = new features being developed. Maintenance-Only = bugfixes only, no new features. Deprecated = scheduled for shutdown."
          >
            <span className={`detail-value${systemAttributes?.status || attrs.status ? ' status-badge' : ''}`}>
              {systemAttributes?.status || attrs.status || 'Unknown'}
            </span>
          </DetailRow>
        )}

        {/* Tier field */}
        {nodeType === 'system' && (
          <DetailRow
            label="Criticality Tier"
            tooltip="Tier 1 = Production Critical (site-wide outage if down). Tier 2 = Standard (specific journey broken). Tier 3 = Internal/Development (minor impact)."
          >
            <span className="detail-value">
              {systemAttributes?.criticality || systemAttributes?.tier || attrs.tier || 'Unknown'}
            </span>
          </DetailRow>
        )}

        {/* Data class field */}
        {nodeType === 'system' && (
          <DetailRow
            label="Data Sensitivity"
            tooltip="PII = names, emails, addresses. Credit-Card = Payment data. Legal/Security = Compliance, audit, encryption. General = Non-sensitive data."
          >
            <span className="detail-value">
              {systemAttributes?.data_class || attrs.data_class || 'Not classified'}
            </span>
          </DetailRow>
        )}

        {/* Active experts */}
        {nodeType === 'system' && (
          <DetailRow
            label="Active Experts (Bus Factor)"
            tooltip="Bus factor: contributors with 3+ commits in last 90 days. 0 = high risk (no active maintainers). 1 = single point of failure. Higher is better."
          >
            {(() => {
              const rawValue = systemAttributes?.active_experts ?? attrs.active_experts;
              const isZero = rawValue === 0;
              const label =
                rawValue == null ? 'Unknown'
                : rawValue === 0 ? 'No active experts'
                : rawValue === 1 ? '1 active expert'
                : `${rawValue} active experts`;
              return (
                <span className={`detail-value active-experts-value ${isZero ? 'active-experts-zero' : ''}`}>
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
                <span style={{ color: '#64748b' }}>({docQuality.score}/100)</span>
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
            <span className="detail-value">{deploymentTargets.join(', ')}</span>
          </DetailRow>
        )}

        {/* Compliance status */}
        {nodeType === 'system' && (
          <DetailRow
            label="Architectural Compliance"
            tooltip="Calculated from: tier-data alignment, ownership, bus factor, and lifecycle. COMPLIANT = proper governance. AT_RISK = ownership/maintenance gaps. NON_COMPLIANT = sensitive data mishandled or abandoned."
          >
            <span className={`detail-value${complianceStatus && complianceStatus !== 'UNKNOWN' ? ' status-badge' : ''}`}>
              {complianceStatus && complianceStatus !== 'UNKNOWN'
                ? (complianceStatusLabel || complianceStatus)
                : 'Not assessed'}
            </span>
          </DetailRow>
        )}

        {/* Compliance confidence */}
        {nodeType === 'system' && complianceConfidencePercent !== undefined && complianceStatus !== 'UNKNOWN' && (
          <DetailRow
            label="Compliance Confidence"
            tooltip="Based on metadata completeness: higher when tier, data classification, and owner are known. Range 50-100%."
          >
            <span className="detail-value">{complianceConfidencePercent}%</span>
          </DetailRow>
        )}

        {/* Compliance factors */}
        {complianceFactors.length > 0 && (
          <DetailRow
            label="Compliance Issues"
            tooltip="Detected architectural risks: sensitive data in low tiers, missing ownership, bus factor concerns, deprecated services with sensitive data, or single points of failure."
          >
            <span className="detail-value">{complianceFactors.join('; ')}</span>
          </DetailRow>
        )}

        {/* Git activity */}
        {nodeType === 'system' && (
          <DetailRow
            label="Git Activity (90d)"
            tooltip="Number of commits in the last 90 days. Low activity on a Tier-1 system may indicate maintenance risk. Shows 'No git access' when the repository was extracted without a .git directory (e.g. from a ZIP download). Re-extract from a proper git clone to populate this field."
          >
            {systemAttributes?.commit_count_90d != null ? (
              <span className="detail-value">
                {systemAttributes.commit_count_90d} commits
                {systemAttributes?.commit_count_30d != null && (
                  <span style={{ color: '#64748b', marginLeft: 8 }}>
                    ({systemAttributes.commit_count_30d} in last 30d)
                  </span>
                )}
              </span>
            ) : (
              <span className="detail-value" style={{ color: '#94a3b8' }}>
                No git access — re-extract from a git clone
              </span>
            )}
          </DetailRow>
        )}

        {/* Last commit date */}
        {nodeType === 'system' && systemAttributes?.last_commit_date && (
          <DetailRow label="Last Commit">
            <span className="detail-value">{systemAttributes.last_commit_date}</span>
          </DetailRow>
        )}

        {/* Node type metadata */}
        {selectedNode?.type && (
          <DetailRow
            label="Type"
            tooltip="Node type: system (entire service), container (API/UI/DB), component (class/module), or external_system (third-party service)."
            className="metadata-row"
          >
            <span className="detail-value">{selectedNode.type}</span>
          </DetailRow>
        )}

        {/* Technology (container) */}
        {selectedNode?.containerMeta?.technology && (
          <DetailRow
            label="Technology"
            tooltip="Primary technology stack: Python/FastAPI, React/TypeScript, PostgreSQL, Redis, etc. Detected from code and dependencies."
            className="metadata-row"
          >
            <span className="detail-value">{selectedNode.containerMeta.technology}</span>
          </DetailRow>
        )}

        {/* Container Type */}
        {(selectedNode?.containerMeta?.container_type || attrs.container_type) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Container Type</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.container_type || attrs.container_type}
            </span>
          </div>
        )}

        {/* Runtime version */}
        {(selectedNode?.containerMeta?.runtime_info || attrs.runtime_info ||
          selectedNode?.containerMeta?.runtime_environment || attrs.runtime_environment) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Runtime</span>
            <span className="detail-value">
              {selectedNode?.containerMeta?.runtime_info || attrs.runtime_info ||
               selectedNode?.containerMeta?.runtime_environment || attrs.runtime_environment}
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
        {(selectedNode?.containerMeta?.health_endpoint || attrs.health_endpoint) && (
          <div className="detail-row metadata-row">
            <span className="detail-label">Health Endpoint</span>
            <span className="detail-value">
              <code className="endpoint-path">
                {selectedNode?.containerMeta?.health_endpoint || attrs.health_endpoint}
              </code>
            </span>
          </div>
        )}

        {/* Container description */}
        {!nodeDescription &&
          (selectedNode?.containerMeta?.description || attrs.description) &&
          selectedNode?.type !== 'system' && (
          <div className="detail-row">
            <span className="detail-value description-text">
              {selectedNode?.containerMeta?.description || attrs.description}
            </span>
          </div>
        )}

        {/* Technology Stack (system-level languages + frameworks) */}
        {((systemAttributes?.languages?.length > 0) || (systemAttributes?.frameworks?.length > 0)) && (
          <DetailRow
            label="Technology Stack"
            tooltip="Languages and frameworks detected across the service's source code and package manifests."
            className="metadata-row"
          >
            <span className="detail-value">
              {[
                ...(systemAttributes?.languages || []),
                ...(systemAttributes?.frameworks || []).map((f: any) =>
                  typeof f === 'string' ? f : f?.name || ''
                ),
              ]
                .filter(Boolean)
                .join(', ') || '—'}
            </span>
          </DetailRow>
        )}

        {/* External Dependencies (system node) */}
        {selectedNode?.type === 'system' &&
          (systemAttributes?.external_dependencies?.length > 0 ||
           attrs.external_dependencies?.length > 0) && (
          <DetailRow
            label="External Dependencies"
            tooltip="Third-party services detected from package manifests: databases, message brokers, cloud services, etc."
          >
            <span className="detail-value">
              {(systemAttributes?.external_dependencies || attrs.external_dependencies || [])
                .map((d: any) =>
                  typeof d === 'string' ? d : `${d.name}${d.type ? ` (${d.type})` : ''}`
                )
                .join(', ')}
            </span>
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
              <a href={attrs.url} target="_blank" rel="noopener noreferrer" className="external-link">
                {attrs.url}
              </a>
            </span>
          </DetailRow>
        )}

        {/* Access endpoint */}
        {(selectedNode?.containerMeta?.endpoint || attrs.endpoint || attrs.access_path) && (
          <DetailRow
            label="Access Endpoint"
            tooltip="The URL path or endpoint used to access this service or UI directly."
          >
            <span className="detail-value">
              <code className="endpoint-path">
                {selectedNode?.containerMeta?.endpoint || attrs.endpoint || attrs.access_path}
              </code>
            </span>
          </DetailRow>
        )}

        {/* Detected from */}
        {attrs.detected_from && (
          <DetailRow
            label="Detected From"
            tooltip="Configuration file where this dependency was found: package.json, requirements.txt, docker-compose.yml, Helm charts, etc."
            className="metadata-row"
          >
            <span className="detail-value">{attrs.detected_from}</span>
          </DetailRow>
        )}

        {/* C4 Classification — only show when known (not UNKNOWN) */}
        {attrs.dependency_type && attrs.dependency_type !== 'UNKNOWN' && (
          <DetailRow
            label="C4 Classification"
            tooltip="BUSINESS_SYSTEM = External business service (should appear at Context level). TECHNICAL_INFRA = Infrastructure component (should appear at Container level). Classified by type inference or LLM."
          >
            <span className={`detail-value pill ${
              attrs.dependency_type === 'BUSINESS_SYSTEM'
                ? 'business-system-pill'
                : 'technical-infra-pill'
            }`}>
              {attrs.dependency_type}
            </span>
          </DetailRow>
        )}

        {/* Classification confidence — only show when known */}
        {attrs.dependency_type && attrs.dependency_type !== 'UNKNOWN' &&
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

        {/* Classification reasoning */}
        {attrs.classification_reasoning && attrs.dependency_type !== 'UNKNOWN' && (
          <DetailRow
            label="Classification Reasoning"
            tooltip="Explanation of why this dependency was classified as business or technical."
          >
            <span className="detail-value">{attrs.classification_reasoning}</span>
          </DetailRow>
        )}

      </div>
    </aside>
  );
}
