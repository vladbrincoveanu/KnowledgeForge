import React from "react";

interface RepoHealthStripProps {
  systemContext: Record<string, any> | null | undefined;
}

type BadgeTone = "danger" | "warn" | "ok" | "neutral";

const STALE_DAYS = 90;
const SINGLE_OWNER_SHARE = 0.8;

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

const Dot: React.FC = () => (
  <span className="repo-health-strip__dot" aria-hidden>·</span>
);

const RepoHealthStrip: React.FC<RepoHealthStripProps> = ({ systemContext: sc }) => {
  if (!sc) return null;

  const tier: string | undefined = sc.criticality || sc.tier;
  const status: string | undefined = sc.status;
  const compliance: string | undefined = sc.compliance;
  const dataClass: string | undefined = sc.data_class;
  const daysSince: number | undefined = sc.days_since_last_commit;
  const busFactor: number | undefined = sc.bus_factor;
  const topContributor: { name?: string; commits?: number } | undefined =
    sc.top_contributor;
  const topShare: number | undefined = sc.top_contributor_share;

  const isStale = typeof daysSince === "number" && daysSince > STALE_DAYS;
  const isSingleOwner =
    busFactor === 1 ||
    (typeof topShare === "number" && topShare > SINGLE_OWNER_SHARE);

  // Don't render the strip if there's nothing useful to show
  const hasSignals =
    tier || status || compliance || dataClass || daysSince !== undefined || busFactor;
  if (!hasSignals) return null;

  return (
    <div className="repo-health-strip">
      {tier && <Badge tone={tierTone(tier)} label={tier} />}
      {status && <Badge tone={statusTone(status)} label={status} />}
      {compliance && (
        <Badge
          tone={complianceTone(compliance)}
          label={compliance.replace("_RISK", "")}
          title={`Compliance: ${compliance}`}
        />
      )}
      {dataClass && dataClass !== "Unknown" && (
        <Badge
          tone={dataClassTone(dataClass)}
          label={dataClass}
          title={`Data class: ${dataClass}`}
        />
      )}

      {(topContributor?.name || daysSince !== undefined || busFactor !== undefined) && (
        <Dot />
      )}

      {isSingleOwner && (
        <Badge
          tone="warn"
          label="Bus factor 1"
          title={
            topContributor?.name && typeof topShare === "number"
              ? `${topContributor.name} authored ${Math.round(topShare * 100)}% of commits`
              : "Single-owner risk"
          }
        />
      )}

      {topContributor?.name && (
        <span className="repo-health-strip__meta">
          Top: <strong>{topContributor.name}</strong>
          {typeof topShare === "number" && (
            <> · {Math.round(topShare * 100)}%</>
          )}
        </span>
      )}

      {daysSince !== undefined && (
        <>
          {topContributor?.name && <Dot />}
          <span
            className={`repo-health-strip__meta${isStale ? " repo-health-strip__meta--stale" : ""}`}
          >
            {daysSince}d since commit
          </span>
        </>
      )}
    </div>
  );
};

export default RepoHealthStrip;
