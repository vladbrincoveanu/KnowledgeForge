import React from "react";

interface KFLogoProps {
  height?: number;
}

export default function KFLogo({ height = 28 }: KFLogoProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.55rem" }}>
      <svg
        viewBox="0 0 32 32"
        style={{ height, width: "auto", color: "#00b8b8", flexShrink: 0 }}
        aria-hidden
      >
        <g fill="currentColor">
          <circle cx="16" cy="5" r="2.6" />
          <circle cx="27" cy="11" r="2.6" />
          <circle cx="27" cy="21" r="2.6" />
          <circle cx="16" cy="27" r="2.6" />
          <circle cx="5" cy="21" r="2.6" />
          <circle cx="5" cy="11" r="2.6" />
        </g>
        <g stroke="currentColor" strokeWidth="1.6" fill="none" opacity="0.9">
          <path d="M16 5 L27 11 L27 21 L16 27 L5 21 L5 11 Z" />
          <path d="M16 5 L16 27 M5 11 L27 21 M27 11 L5 21" opacity="0.55" />
        </g>
      </svg>
      <span
        style={{
          fontWeight: 700,
          fontSize: "1.25rem",
          letterSpacing: "-0.02em",
          lineHeight: 1,
          color: "#0f172a",
        }}
      >
        knowledge<span style={{ color: "#00b8b8" }}>forge</span>
      </span>
    </div>
  );
}
