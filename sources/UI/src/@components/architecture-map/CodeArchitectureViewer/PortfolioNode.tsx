import React, { memo } from "react";
import { Handle, Position } from "reactflow";

interface PortfolioNodeProps {
  data: {
    label: string;
    systemName?: string;
    repoUrl?: string | null;
    containersCount?: number;
    componentsCount?: number;
    completedAt?: string | null;
    // Manager signals
    tier?: string;
    status?: string;
    compliance?: string;
    dataClass?: string;
    daysSinceLastCommit?: number | null;
    busFactor?: number | null;
    contributorCount?: number | null;
    topContributorShare?: number | null;
    topContributor?: { name?: string; commits?: number } | null;
  };
}

type BadgeTone = "danger" | "warn" | "ok" | "neutral";

const tierTone = (tier?: string): BadgeTone => {
  if (tier === "Tier 1") return "danger";
  if (tier === "Tier 2") return "warn";
  if (tier === "Tier 3") return "ok";
  return "neutral";
};

const statusTone = (status?: string): BadgeTone => {
  if (status === "ACTIVE") return "ok";
  if (status === "MAINTENANCE") return "warn";
  if (status === "DEPRECATED" || status === "ARCHIVED") return "danger";
  return "neutral";
};

const complianceTone = (c?: string): BadgeTone => {
  if (c === "HIGH_RISK") return "danger";
  if (c === "MEDIUM_RISK") return "warn";
  if (c === "LOW_RISK") return "ok";
  return "neutral";
};

const dataClassTone = (d?: string): BadgeTone => {
  if (d === "PII" || d === "Credit-Card") return "danger";
  if (d === "Internal") return "warn";
  if (d === "Public") return "neutral";
  return "neutral";
};

const Badge: React.FC<{ tone: BadgeTone; label: string; title?: string }> = ({
  tone,
  label,
  title,
}) => (
  <span className={`pn-badge pn-badge--${tone}`} title={title || label}>
    {label}
  </span>
);

const STALE_DAYS = 90;
const SINGLE_OWNER_SHARE = 0.8;

const PortfolioNode: React.FC<PortfolioNodeProps> = memo(({ data }) => {
  const {
    label,
    systemName,
    containersCount = 0,
    componentsCount = 0,
    tier,
    status,
    compliance,
    dataClass,
    daysSinceLastCommit,
    busFactor,
    topContributorShare,
    topContributor,
  } = data;

  const repoShort = label.includes("/") ? label.split("/")[1] : label;
  const repoOwner = label.includes("/") ? label.split("/")[0] : "";

  const isStale =
    typeof daysSinceLastCommit === "number" && daysSinceLastCommit > STALE_DAYS;
  const isSingleOwner =
    busFactor === 1 ||
    (typeof topContributorShare === "number" &&
      topContributorShare > SINGLE_OWNER_SHARE);

  // Border tone reflects the worst signal we observe.
  let borderTone: BadgeTone = "neutral";
  if (
    tier === "Tier 1" ||
    compliance === "HIGH_RISK" ||
    dataClass === "PII" ||
    dataClass === "Credit-Card" ||
    status === "DEPRECATED" ||
    status === "ARCHIVED"
  ) {
    borderTone = "danger";
  } else if (
    tier === "Tier 2" ||
    compliance === "MEDIUM_RISK" ||
    status === "MAINTENANCE" ||
    isStale ||
    isSingleOwner
  ) {
    borderTone = "warn";
  } else if (status === "ACTIVE" && compliance === "LOW_RISK") {
    borderTone = "ok";
  }

  return (
    <div className={`portfolio-node portfolio-node--${borderTone}`}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      <div className="portfolio-node__body">
        <div className="portfolio-node__name">
          {repoOwner && (
            <span className="portfolio-node__owner">{repoOwner}/</span>
          )}
          <span className="portfolio-node__repo">{repoShort}</span>
        </div>

        {systemName && systemName !== label && (
          <div className="portfolio-node__system">{systemName}</div>
        )}

        <div className="portfolio-node__badges">
          {tier && <Badge tone={tierTone(tier)} label={tier} />}
          {status && <Badge tone={statusTone(status)} label={status} />}
          {compliance && (
            <Badge
              tone={complianceTone(compliance)}
              label={compliance.replace("_RISK", "")}
              title={`Compliance: ${compliance}`}
            />
          )}
          {dataClass && (
            <Badge
              tone={dataClassTone(dataClass)}
              label={dataClass}
              title={`Data class: ${dataClass}`}
            />
          )}
          {isStale && (
            <Badge
              tone="warn"
              label={`Stale ${daysSinceLastCommit}d`}
              title={`No commits in ${daysSinceLastCommit} days`}
            />
          )}
          {isSingleOwner && (
            <Badge
              tone="warn"
              label="Bus factor 1"
              title={
                topContributor?.name
                  ? `${topContributor.name} authored ${Math.round((topContributorShare ?? 0) * 100)}% of commits`
                  : "Single-owner risk"
              }
            />
          )}
        </div>

        <div className="portfolio-node__meta">
          <span className="portfolio-node__pill">{containersCount} containers</span>
          <span className="portfolio-node__pill">{componentsCount} components</span>
        </div>

        {topContributor?.name && (
          <div className="portfolio-node__owner-line">
            Top: <strong>{topContributor.name}</strong>
            {typeof topContributorShare === "number" && (
              <> · {Math.round(topContributorShare * 100)}%</>
            )}
          </div>
        )}

        <div className="portfolio-node__hint">zoom in to explore →</div>
      </div>
    </div>
  );
});

PortfolioNode.displayName = "PortfolioNode";
export default PortfolioNode;
