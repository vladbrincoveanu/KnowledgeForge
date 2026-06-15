import React, { useMemo } from "react";

export type PortfolioSignalFilter =
  | "tier1"
  | "high_risk"
  | "pii"
  | "stale"
  | "single_owner"
  | "deprecated";

interface ExtractionEntry {
  task_id: string;
  tier?: string;
  status?: string;
  compliance?: string;
  data_class?: string;
  days_since_last_commit?: number | null;
  bus_factor?: number | null;
  top_contributor_share?: number | null;
}

interface PortfolioSummaryProps {
  extractions: ExtractionEntry[];
  activeFilter: PortfolioSignalFilter | null;
  onToggleFilter: (filter: PortfolioSignalFilter | null) => void;
}

const STALE_DAYS = 90;
const SINGLE_OWNER_SHARE = 0.8;

const matchers: Record<PortfolioSignalFilter, (e: ExtractionEntry) => boolean> = {
  tier1: (e) => e.tier === "Tier 1",
  high_risk: (e) => e.compliance === "HIGH_RISK",
  pii: (e) => e.data_class === "PII" || e.data_class === "Credit-Card",
  stale: (e) =>
    typeof e.days_since_last_commit === "number" &&
    e.days_since_last_commit > STALE_DAYS,
  single_owner: (e) =>
    e.bus_factor === 1 ||
    (typeof e.top_contributor_share === "number" &&
      e.top_contributor_share > SINGLE_OWNER_SHARE),
  deprecated: (e) => e.status === "DEPRECATED" || e.status === "ARCHIVED",
};

const PortfolioSummary: React.FC<PortfolioSummaryProps> = ({
  extractions,
  activeFilter,
  onToggleFilter,
}) => {
  const counts = useMemo(() => {
    const out: Record<PortfolioSignalFilter, number> = {
      tier1: 0,
      high_risk: 0,
      pii: 0,
      stale: 0,
      single_owner: 0,
      deprecated: 0,
    };
    for (const e of extractions) {
      (Object.keys(matchers) as PortfolioSignalFilter[]).forEach((key) => {
        if (matchers[key](e)) out[key] += 1;
      });
    }
    return out;
  }, [extractions]);

  const total = extractions.length;

  const chips: Array<{
    key: PortfolioSignalFilter;
    label: string;
    tone: "danger" | "warn";
  }> = [
    { key: "tier1", label: "Tier 1", tone: "danger" },
    { key: "high_risk", label: "High risk", tone: "danger" },
    { key: "pii", label: "PII / Card", tone: "danger" },
    { key: "stale", label: `Stale (>${STALE_DAYS}d)`, tone: "warn" },
    { key: "single_owner", label: "Single-owner", tone: "warn" },
    { key: "deprecated", label: "Deprecated", tone: "warn" },
  ];

  const handleClick = (key: PortfolioSignalFilter) => {
    onToggleFilter(activeFilter === key ? null : key);
  };

  return (
    <div className="portfolio-summary">
      <div className="portfolio-summary__total">
        <strong>{total}</strong> {total === 1 ? "system" : "systems"}
        {activeFilter && (
          <button
            className="portfolio-summary__clear"
            onClick={() => onToggleFilter(null)}
          >
            clear filter
          </button>
        )}
      </div>
      <div className="portfolio-summary__chips">
        {chips.map((chip) => {
          const count = counts[chip.key];
          const isActive = activeFilter === chip.key;
          const disabled = count === 0 && !isActive;
          return (
            <button
              key={chip.key}
              className={`portfolio-summary__chip portfolio-summary__chip--${chip.tone}${
                isActive ? " portfolio-summary__chip--active" : ""
              }`}
              onClick={() => handleClick(chip.key)}
              disabled={disabled}
              type="button"
            >
              <span className="portfolio-summary__chip-count">{count}</span>
              <span className="portfolio-summary__chip-label">{chip.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default PortfolioSummary;
