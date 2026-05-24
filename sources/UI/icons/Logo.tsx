export const Logo = ({ className = "h-7" }: { className?: string }) => (
  <a href="#top" className="flex items-center gap-2.5" aria-label="KnowledgeForge home">
    <svg
      viewBox="0 0 32 32"
      className={`${className} w-auto text-teal-bright`}
      aria-hidden
    >
      {/* Hexagonal node graph mark */}
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
    <span className="font-bold text-foreground tracking-tight text-[1.05rem] leading-none">
      knowledge<span className="text-teal-bright">forge</span>
    </span>
  </a>
);
