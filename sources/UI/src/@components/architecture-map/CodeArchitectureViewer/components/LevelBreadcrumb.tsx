import React from "react";

interface LevelBreadcrumbProps {
  selectedLevel: string;
  repoName: string | null;
  onNavigate: (level: string) => void;
}

interface Crumb {
  label: string;
  level: string;
  active: boolean;
}

export default function LevelBreadcrumb({
  selectedLevel,
  repoName,
  onNavigate,
}: LevelBreadcrumbProps) {
  const crumbs: Crumb[] = [];

  crumbs.push({
    label: "Portfolio",
    level: "portfolio_level",
    active: selectedLevel === "portfolio_level",
  });

  if (selectedLevel !== "portfolio_level") {
    const short = repoName
      ? repoName.includes("/")
        ? repoName.split("/")[1]
        : repoName
      : "Project";
    crumbs.push({
      label: short,
      level: "context_level",
      active: selectedLevel === "context_level",
    });
  }

  if (selectedLevel === "container_level") {
    crumbs.push({ label: "Container", level: "container_level", active: true });
  }

  if (selectedLevel === "component_level") {
    crumbs.push(
      { label: "Container", level: "container_level", active: false },
      { label: "Component", level: "component_level", active: true },
    );
  }

  if (crumbs.length <= 1) return null;

  return (
    <nav className="level-breadcrumb" aria-label="Level navigation">
      {crumbs.map((crumb, idx) => (
        <React.Fragment key={crumb.level}>
          {idx > 0 && (
            <span className="level-breadcrumb__sep" aria-hidden="true">
              ›
            </span>
          )}
          {crumb.active ? (
            <span className="level-breadcrumb__item level-breadcrumb__item--active">
              {crumb.label}
            </span>
          ) : (
            <button
              className="level-breadcrumb__item level-breadcrumb__item--link"
              onClick={() => onNavigate(crumb.level)}
            >
              {crumb.label}
            </button>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
