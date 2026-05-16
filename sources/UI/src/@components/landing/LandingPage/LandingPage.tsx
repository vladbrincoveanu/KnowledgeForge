import React, { useMemo, useState } from "react";

/* ─────────────────────────────────────────────────────────────────────────────
 * EMAIL OBFUSCATION — client-side only; raw strings never appear in HTML source
 * Scheme: shift char codes +1, then reverse — so @ and . never appear literally
 * ───────────────────────────────────────────────────────────────────────────── */
const encodeEmail = (s: string) =>
  s
    .split("")
    .map((c) => String.fromCharCode(c.charCodeAt(0) + 1))
    .reverse()
    .join("");

const decodeEmail = (encoded: string) =>
  encoded
    .split("")
    .reverse()
    .map((c) => String.fromCharCode(c.charCodeAt(0) - 1))
    .join("");

const MailTo: React.FC<{
  encoded: string;
  className?: string;
  children: React.ReactNode;
}> = ({ encoded, className, children }) => (
  <a href={`mailto:${decodeEmail(encoded)}`} className={className}>
    {children}
  </a>
);
import {
  AlarmClock,
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Code2,
  Database,
  Download,
  Eye,
  GitBranch,
  Layers,
  Link2,
  MessageCircle,
  Monitor,
  Network,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  UserCheck,
  Users2,
  XCircle,
} from "lucide-react";
import "./LandingPage.scss";

/* ─────────────────────────────────────────────────────────────────────────────
 * SECTION DATA
 * ───────────────────────────────────────────────────────────────────────────── */

const STATS = [
  {
    value: "$6T",
    label: "Global Technical Debt",
    detail:
      "Roughly doubled between 2012 and 2023. Most of it invisible, none of it on a map.",
    source: "Oliver Wyman · 2024",
  },
  {
    value: "$4.88M",
    label: "Average Breach Cost",
    detail:
      "Supply-chain exposure is unmanageable without a dependency map that links code to business systems.",
    source: "IBM · 2024",
  },
  {
    value: "25%",
    label: "Dev Time on Toil",
    detail:
      "A full day a week lost to searching for answers the architecture should already expose.",
    source: "Sonar Source Report · 2026",
  },
];

const OPERATOR_PAIN_POINTS = [
  {
    icon: <AlertTriangle size={16} />,
    text: '"What breaks if I change this service?"',
  },
  {
    icon: <Eye size={16} />,
    text: "Can't see downstream dependencies across repos.",
  },
  {
    icon: <AlarmClock size={16} />,
    text: "Onboarding a new engineer drags from days into months.",
  },
  {
    icon: <Link2 size={16} />,
    text: "Duplicated services built by teams that can't see each other.",
  },
];

const COMMANDER_PAIN_POINTS = [
  {
    icon: <Users2 size={16} />,
    text: '"What does our engineering organization actually run?"',
  },
  {
    icon: <Network size={16} />,
    text: "M&A integrations guess at system redundancy.",
  },
  {
    icon: <ShieldAlert size={16} />,
    text: "Vulnerabilities get triaged without knowing blast radius.",
  },
  {
    icon: <MessageCircle size={16} />,
    text: "Decisions rely on tribal knowledge.",
  },
];

const PILLARS = [
  {
    icon: <GitBranch size={20} />,
    title: "Accurate Graph",
    description:
      "We read your repositories directly and build the graph from the ground truth — the code itself.",
  },
  {
    icon: <RefreshCw size={20} />,
    title: "Self-Updating",
    description:
      "The map refreshes with every commit, PR, and redeploy. No outdated wikis. No catalogs to maintain by hand.",
  },
  {
    icon: <MessageCircle size={20} />,
    title: "Queryable in Plain English",
    description:
      "LLMs on top of the graph let anyone explore the estate and extract insights using natural language.",
  },
  {
    icon: <Boxes size={20} />,
    title: "One Source of Truth",
    description:
      "Developers see the system. Leadership sees the portfolio. Same living ontology, rendered at different altitudes.",
  },
];

const ALTITUDES = [
  {
    level: "L1",
    name: "Ecosystem View",
    persona: "CIO / Board",
    description:
      "Your software in context. External systems, users, and data flows at a glance. Vendor risk and regulatory exposure mapped to business capabilities — not repo names.",
    mockup: "context",
  },
  {
    level: "L2",
    name: "Service View",
    persona: "Architect / Tech Lead",
    description:
      "The major moving parts inside your system and how they connect. Simulate blast-radius before a change lands, instead of discovering it in production.",
    mockup: "service",
  },
  {
    level: "L3",
    name: "Internals View",
    persona: "Developer / SRE",
    description:
      "Inside each service. The real building blocks developers work with daily — classes, functions, execution paths — with deep links back to Git. Onboarding from months to hours.",
    mockup: "code",
  },
];

const PIPELINE_STEPS = [
  {
    number: "1",
    name: "Ingest",
    description:
      "Webhook-driven Git repository ingestion. Multi-language, zero config.",
    icon: <Download size={18} />,
  },
  {
    number: "2",
    name: "Parse",
    description:
      "Tree-sitter for deterministic AST analysis. LLMs resolve intent and cross-file dependencies.",
    icon: <Code2 size={18} />,
  },
  {
    number: "3",
    name: "Model",
    description:
      "Map data to a standardized C4 ontology — Context, Container, Component, Code.",
    icon: <Layers size={18} />,
  },
  {
    number: "4",
    name: "Store",
    description:
      "Relationships as first-class citizens in Neo4j for high-performance multi-hop queries.",
    icon: <Database size={18} />,
  },
  {
    number: "5",
    name: "Serve",
    description:
      "Render three views — Ecosystem, Service, Internals — with zero manual input.",
    icon: <Monitor size={18} />,
  },
];

const PLATFORM_STAGES = [
  {
    number: "1",
    name: "Structure",
    tagline: "Code read directly.",
    description:
      "Deterministic extraction. Every service, every dependency, every change — without human mediation.",
    icon: <Code2 size={24} />,
    color: "blue",
  },
  {
    number: "2",
    name: "Intelligence",
    tagline: "Senior architect context.",
    description:
      "AI enriches the structure with architectural insight. The AI never modifies the structural foundation.",
    icon: <Sparkles size={24} />,
    color: "indigo",
  },
  {
    number: "3",
    name: "Judgement",
    tagline: "Human in the loop.",
    description:
      "Edge cases routed to a human reviewer. Input is front-loaded and diminishes as the system learns your organisation.",
    icon: <UserCheck size={24} />,
    color: "green",
  },
];

const RISKS = [
  {
    icon: <UserCheck size={20} />,
    title: "Key-Person Risk",
    stat: "40%",
    statCaption: "slower feature delivery for high-debt teams",
    description:
      "Betweenness centrality exposes engineers who own critical paths. We tell you who to cross-train — before they leave.",
    source: "McKinsey · 2023",
  },
  {
    icon: <ShieldAlert size={20} />,
    title: "Supply-Chain Risk",
    stat: "$4.88M",
    statCaption: "average data breach cost",
    description:
      "When a new CVE drops, we trace it through the graph to the exposed business systems — blast-radius context, not alert fatigue.",
    source: "IBM · 2024",
  },
  {
    icon: <AlertTriangle size={20} />,
    title: "Technical Debt",
    stat: "$6T",
    statCaption: "global technical debt, doubled since 2012",
    description:
      "We identify architectural debt — not just code smells. The coupling patterns and bottlenecks that actually throttle deploy velocity.",
    source: "Oliver Wyman · 2024",
  },
  {
    icon: <Boxes size={20} />,
    title: "Lifecycle Waste",
    stat: "25%",
    statCaption: "of dev time lost to toil work",
    description:
      "We eliminate the toil tax. A living, queryable graph means developers stop spending hours a week hunting for answers.",
    source: "Sonar Source Report · 2026",
  },
];

const FOUNDERS = [
  {
    initials: "IR",
    name: "Iulia Rinea",
    title: "Co-founder",
    bio: "Leads data and AI platform work at AI Factory Austria. Production ML infrastructure at scale.",
    email: encodeEmail("rineaiulia17@gmail.com"),
    seed: 42,
  },
  {
    initials: "VB",
    name: "Vlad Brincoveanu",
    title: "Co-founder",
    bio: "Works in distributed systems at CID. The kind of engineering that sits underneath everything else and cannot afford to fail.",
    email: encodeEmail("ggvladbrincoveanu@gmail.com"),
    seed: 17,
  },
];

/* ─────────────────────────────────────────────────────────────────────────────
 * ANIMATED SVG GRAPH CANVAS
 * ───────────────────────────────────────────────────────────────────────────── */

// Seeded pseudo-random for deterministic node positions
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

interface GraphNode {
  id: number;
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
}

interface GraphEdge {
  from: number;
  to: number;
}

function buildGraph() {
  const rand = seededRandom(42);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  // Generate nodes — denser in center
  for (let i = 0; i < 32; i++) {
    const angle = rand() * Math.PI * 2;
    const distFactor = Math.pow(rand(), 0.6); // bias toward center
    const x = 45 + distFactor * Math.cos(angle) * 38;
    const y = 40 + distFactor * Math.sin(angle) * 32;
    nodes.push({
      id: i,
      x,
      y,
      r: 3 + rand() * 5,
      vx: (rand() - 0.5) * 0.015,
      vy: (rand() - 0.5) * 0.015,
    });
  }

  // Generate edges — connect nearby nodes
  for (let i = 0; i < nodes.length; i++) {
    const connections = 1 + Math.floor(rand() * 3);
    for (let c = 0; c < connections; c++) {
      let j = Math.floor(rand() * nodes.length);
      if (j !== i) {
        const edgeExists = edges.some(
          (e) => (e.from === i && e.to === j) || (e.from === j && e.to === i),
        );
        if (!edgeExists) {
          edges.push({ from: i, to: j });
        }
      }
    }
  }

  return { nodes, edges };
}

const { nodes: GRAPH_NODES, edges: GRAPH_EDGES } = buildGraph();

/* ─────────────────────────────────────────────────────────────────────────────
 * GEOMETRIC FOUNDER AVATAR
 * ───────────────────────────────────────────────────────────────────────────── */

const GeometricAvatar: React.FC<{ initials: string; seed: number }> = ({
  initials,
  seed,
}) => {
  // Deterministic "randomness" from seed
  const pseudoRandom = (s: number) => {
    const x = Math.sin(s) * 10000;
    return x - Math.floor(x);
  };

  const shapes = [];
  const shapeCount = 5;
  for (let i = 0; i < shapeCount; i++) {
    const angle = pseudoRandom(seed + i * 37) * 360;
    const dist = 8 + pseudoRandom(seed + i * 13) * 10;
    const size = 3 + pseudoRandom(seed + i * 7) * 6;
    const opacity = 0.08 + pseudoRandom(seed + i * 19) * 0.12;
    const cx = 28 + Math.cos((angle * Math.PI) / 180) * dist;
    const cy = 28 + Math.sin((angle * Math.PI) / 180) * dist;
    shapes.push({ cx, cy, r: size, opacity });
  }

  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 56 56"
      fill="none"
      aria-hidden="true"
      style={{ display: "block" }}
    >
      <defs>
        <radialGradient id={`grad-${seed}`} cx="30%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="50%" stopColor="#1D4ED8" />
          <stop offset="100%" stopColor="#1E3A8A" />
        </radialGradient>
        <radialGradient id={`inner-glow-${seed}`} cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#60A5FA" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Base circle with gradient */}
      <circle cx="28" cy="28" r="28" fill={`url(#grad-${seed})`} />

      {/* Inner glow */}
      <circle cx="28" cy="28" r="28" fill={`url(#inner-glow-${seed})`} />

      {/* Geometric network lines */}
      <g stroke="rgba(255,255,255,0.12)" strokeWidth="0.75" fill="none">
        {/* Hexagonal inner ring */}
        <polygon
          points="28,14 38.5,21 38.5,35 28,42 17.5,35 17.5,21"
          strokeOpacity="0.2"
        />
        {/* Inner triangle */}
        <polygon points="28,18 35,32 21,32" strokeOpacity="0.15" />
        {/* Center to corners */}
        <line x1="28" y1="28" x2="28" y2="14" strokeOpacity="0.15" />
        <line x1="28" y1="28" x2="38.5" y2="21" strokeOpacity="0.15" />
        <line x1="28" y1="28" x2="38.5" y2="35" strokeOpacity="0.15" />
        <line x1="28" y1="28" x2="28" y2="42" strokeOpacity="0.15" />
        <line x1="28" y1="28" x2="17.5" y2="35" strokeOpacity="0.15" />
        <line x1="28" y1="28" x2="17.5" y2="21" strokeOpacity="0.15" />
      </g>

      {/* Abstract decorative dots */}
      {shapes.map((shape, i) => (
        <circle
          key={i}
          cx={shape.cx}
          cy={shape.cy}
          r={shape.r}
          fill="rgba(255,255,255,0.25)"
          opacity={shape.opacity}
        />
      ))}

      {/* Highlight arc */}
      <ellipse
        cx="22"
        cy="18"
        rx="8"
        ry="5"
        fill="rgba(255,255,255,0.12)"
        transform="rotate(-30 22 18)"
      />

      {/* Initials */}
      <text
        x="28"
        y="33"
        textAnchor="middle"
        fill="rgba(255,255,255,0.9)"
        fontSize="14"
        fontWeight="700"
        fontFamily="Plus Jakarta Sans, sans-serif"
        letterSpacing="0.05em"
      >
        {initials}
      </text>
    </svg>
  );
};

/* ─────────────────────────────────────────────────────────────────────────────
 * COMPONENTS
 * ───────────────────────────────────────────────────────────────────────────── */

const Navbar: React.FC = () => (
  <nav className="lp-navbar" role="navigation" aria-label="Main navigation">
    <div className="lp-navbar__inner">
      <div className="lp-navbar__logo">
        <svg
          width="28"
          height="28"
          viewBox="0 0 28 28"
          fill="none"
          aria-hidden="true"
        >
          <polygon
            points="14,2 26,8 26,20 14,26 2,20 2,8"
            stroke="#22C55E"
            strokeWidth="1.5"
            fill="none"
          />
          <circle cx="14" cy="14" r="3" fill="#3B82F6" />
          <line
            x1="14"
            y1="2"
            x2="14"
            y2="11"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
          <line
            x1="14"
            y1="17"
            x2="14"
            y2="26"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
          <line
            x1="2"
            y1="8"
            x2="11"
            y2="12.5"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
          <line
            x1="17"
            y1="15.5"
            x2="26"
            y2="20"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
          <line
            x1="26"
            y1="8"
            x2="17"
            y2="12.5"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
          <line
            x1="11"
            y1="15.5"
            x2="2"
            y2="20"
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.6"
          />
        </svg>
        <span>KnowledgeForge</span>
      </div>
      <div className="lp-navbar__links">
        <a href="#solution">Solution</a>
        <a href="#product">Product</a>
        <a href="#engine">Engine</a>
        <a href="#partners">Partners</a>
      </div>
      <div className="lp-navbar__actions">
        <MailTo
          encoded="mnbpD@mbjbnhplb!dpnqpvBjmvh"
          className="lp-btn lp-btn--ghost"
        >
          Contact Sales
        </MailTo>
        <a href="/workspace" className="lp-btn lp-btn--text">
          Login
        </a>
      </div>
    </div>
  </nav>
);

const AnimatedGraphCanvas: React.FC = () => (
  <div className="lp-graph-canvas" aria-hidden="true">
    <svg
      viewBox="0 0 100 85"
      preserveAspectRatio="xMidYMid slice"
      className="lp-graph-svg"
    >
      <defs>
        <filter id="node-glow">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="canvas-vignette" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stopColor="#0F172A" stopOpacity="0" />
          <stop offset="60%" stopColor="#0F172A" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#0F172A" stopOpacity="0.85" />
        </radialGradient>
      </defs>

      {/* Edges */}
      <g className="lp-graph-edges">
        {GRAPH_EDGES.map((edge, i) => {
          const n1 = GRAPH_NODES[edge.from];
          const n2 = GRAPH_NODES[edge.to];
          return (
            <line
              key={i}
              x1={n1.x}
              y1={n1.y}
              x2={n2.x}
              y2={n2.y}
              stroke="#1E40AF"
              strokeWidth="0.4"
              opacity="0.5"
              className="lp-graph-edge"
            />
          );
        })}
      </g>

      {/* Nodes */}
      <g className="lp-graph-nodes">
        {GRAPH_NODES.map((node) => (
          <circle
            key={node.id}
            cx={node.x}
            cy={node.y}
            r={node.r}
            fill="#3B82F6"
            filter="url(#node-glow)"
            className="lp-graph-node"
            style={{
              // Deterministic animation delay based on node id
              animationDelay: `${(node.id * 0.37) % 5}s`,
            }}
          />
        ))}
      </g>

      {/* Vignette overlay */}
      <rect
        x="0"
        y="0"
        width="100"
        height="85"
        fill="url(#canvas-vignette)"
        pointerEvents="none"
      />
    </svg>
  </div>
);

const HeroSection: React.FC = () => (
  <section className="lp-hero" aria-label="Hero">
    <div className="lp-hero__inner">
      <div className="lp-hero__copy">
        <span className="lp-eyebrow">Automated Architectural Intelligence</span>
        <h1>Bridging the gap between engineering and leadership.</h1>
        <p className="lp-hero__lede">
          KnowledgeForge turns your source code into a living map of your
          software. Self-updating, queryable in plain English, and accurate at
          every altitude — from boardroom to function call.
        </p>
        <div className="lp-hero__actions">
          <a href="#partners" className="lp-btn lp-btn--primary lp-btn--pill">
            <span>Become a Design Partner</span>
            <ArrowRight size={16} />
          </a>
          <a href="#product" className="lp-btn lp-btn--ghost lp-btn--pill">
            <span>See the Product</span>
            <ArrowRight size={16} />
          </a>
        </div>
        <div className="lp-hero__note">
          <CheckCircle2 size={15} />
          <span>
            MVP live. Extraction engine running across multi-language codebases
            today.
          </span>
        </div>
      </div>
      <div className="lp-hero__graph">
        <AnimatedGraphCanvas />
      </div>
    </div>
  </section>
);

const StatCard: React.FC<(typeof STATS)[number]> = ({
  value,
  label,
  detail,
  source,
}) => (
  <article className="lp-stat-card">
    <span className="lp-stat-card__value">{value}</span>
    <h2 className="lp-stat-card__label">{label}</h2>
    <p className="lp-stat-card__detail">{detail}</p>
    <span className="lp-stat-card__source">{source}</span>
  </article>
);

const BlindSpotCard: React.FC<{
  title: string;
  subtitle: string;
  accent: "blue" | "slate";
  painPoints: typeof OPERATOR_PAIN_POINTS;
}> = ({ title, subtitle, accent, painPoints }) => (
  <article className={`lp-blind-card lp-blind-card--${accent}`}>
    <div className="lp-blind-card__header">
      <h2>{title}</h2>
      <span className="lp-blind-card__subtitle">{subtitle}</span>
    </div>
    <ul className="lp-blind-card__list">
      {painPoints.map((point, i) => (
        <li key={i} className="lp-blind-card__item">
          <span className="lp-blind-card__icon">{point.icon}</span>
          <span>{point.text}</span>
        </li>
      ))}
    </ul>
  </article>
);

const PillarCard: React.FC<(typeof PILLARS)[number]> = ({
  icon,
  title,
  description,
}) => (
  <article className="lp-pillar-card">
    <span className="lp-pillar-card__icon">{icon}</span>
    <h3>{title}</h3>
    <p>{description}</p>
  </article>
);

const AltitudeTabSwitcher: React.FC = () => {
  const [active, setActive] = useState(0);
  const altitude = ALTITUDES[active];

  return (
    <div className="lp-altitude" id="product">
      <div className="lp-altitude__tabs" role="tablist">
        {ALTITUDES.map((a, i) => (
          <button
            key={a.level}
            role="tab"
            aria-selected={active === i}
            className={`lp-altitude__tab ${active === i ? "lp-altitude__tab--active" : ""}`}
            onClick={() => setActive(i)}
          >
            <span className="lp-altitude__tab-level">{a.level}</span>
            <span className="lp-altitude__tab-name">{a.name}</span>
          </button>
        ))}
      </div>
      <div className="lp-altitude__panel" role="tabpanel">
        <div className="lp-altitude__info">
          <span className="lp-badge">{altitude.persona}</span>
          <h2>{altitude.name}</h2>
          <p>{altitude.description}</p>
        </div>
        <div className="lp-altitude__mockup">
          <MockupView
            type={altitude.mockup}
            level={altitude.level}
            name={altitude.name}
          />
        </div>
      </div>
    </div>
  );
};

const MockupView: React.FC<{ type: string }> = ({ type }) => {
  const defs = useMemo(
    () => (
      <>
        <defs>
          <pattern
            id="grid"
            width="20"
            height="20"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 20 0 L 0 0 0 20"
              fill="none"
              stroke="rgba(255,255,255,0.04)"
              strokeWidth="0.5"
            />
          </pattern>
          <filter id="glow-blue" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-green" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-indigo" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="shadow-node" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              dx="0"
              dy="2"
              stdDeviation="3"
              floodColor="#000"
              floodOpacity="0.4"
            />
          </filter>
          <radialGradient id="bg-glow-blue" cx="35%" cy="40%" r="65%">
            <stop offset="0%" stopColor="#1D4ED8" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0F172A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="bg-glow-green" cx="35%" cy="40%" r="65%">
            <stop offset="0%" stopColor="#166534" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0F172A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="bg-glow-indigo" cx="35%" cy="40%" r="65%">
            <stop offset="0%" stopColor="#4338CA" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#0F172A" stopOpacity="0" />
          </radialGradient>
          <marker
            id="arrow-blue"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L6,3 z" fill="#3B82F6" opacity="0.7" />
          </marker>
          <marker
            id="arrow-green"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L6,3 z" fill="#22C55E" opacity="0.7" />
          </marker>
          <marker
            id="arrow-indigo"
            markerWidth="5"
            markerHeight="5"
            refX="4"
            refY="2.5"
            orient="auto"
          >
            <path d="M0,0 L0,5 L5,2.5 z" fill="#818CF8" opacity="0.6" />
          </marker>
        </defs>
      </>
    ),
    [],
  );

  // ── L1: SYSTEM CONTEXT / ECOSYSTEM ────────────────────────────────────────
  // Proper C4 L1: people (actors) + the system as a single black box +
  // external third-party systems it talks to. No internals.
  if (type === "context") {
    const actors = [
      { cx: 28, cy: 45, label: "User" },
      { cx: 28, cy: 110, label: "Admin" },
    ];
    const externals = [
      { cx: 290, cy: 28, label: "Stripe", tag: "PAY" },
      { cx: 290, cy: 62, label: "Auth0", tag: "AUTH" },
      { cx: 290, cy: 96, label: "Datadog", tag: "OBS" },
      { cx: 290, cy: 130, label: "SendGrid", tag: "MAIL" },
    ];

    return (
      <svg viewBox="0 0 320 160" className="lp-mockup-svg" aria-hidden="true">
        {defs}
        <rect width="320" height="160" rx="12" fill="#0a0f1e" />
        <rect width="320" height="160" rx="12" fill="url(#bg-glow-blue)" />
        <rect width="320" height="160" rx="12" fill="url(#grid)" />
        <ellipse
          cx="160"
          cy="80"
          rx="100"
          ry="60"
          fill="#1D4ED8"
          opacity="0.05"
        />

        {/* Actors → System arrows */}
        {actors.map((a, i) => (
          <line
            key={`aa${i}`}
            x1={a.cx + 10}
            y1={a.cy}
            x2="108"
            y2={a.cy}
            stroke="#3B82F6"
            strokeWidth="1"
            opacity="0.55"
            markerEnd="url(#arrow-blue)"
          />
        ))}

        {/* Actors (people) */}
        {actors.map((a, i) => (
          <g key={`a${i}`}>
            {/* Head */}
            <circle
              cx={a.cx}
              cy={a.cy - 6}
              r="4.5"
              fill="#1E293B"
              stroke="#60A5FA"
              strokeWidth="1"
            />
            {/* Shoulders / body */}
            <path
              d={`M ${a.cx - 8} ${a.cy + 10} Q ${a.cx - 8} ${a.cy - 2} ${a.cx} ${a.cy - 2} Q ${a.cx + 8} ${a.cy - 2} ${a.cx + 8} ${a.cy + 10} Z`}
              fill="#1E293B"
              stroke="#60A5FA"
              strokeWidth="1"
            />
            <text
              x={a.cx}
              y={a.cy + 22}
              textAnchor="middle"
              fill="#94A3B8"
              fontSize="6"
              fontFamily="Plus Jakarta Sans, sans-serif"
              fontWeight="500"
            >
              {a.label}
            </text>
            <text
              x={a.cx}
              y={a.cy + 30}
              textAnchor="middle"
              fill="#475569"
              fontSize="4"
              fontFamily="monospace"
            >
              [Person]
            </text>
          </g>
        ))}

        {/* The System — one black box in the middle */}
        <g filter="url(#shadow-node)">
          <rect
            x="106"
            y="38"
            width="112"
            height="84"
            rx="10"
            fill="#3B82F6"
            opacity="0.12"
            filter="url(#glow-blue)"
          />
          <rect
            x="108"
            y="40"
            width="108"
            height="80"
            rx="8"
            fill="#1E293B"
            stroke="#60A5FA"
            strokeWidth="1.5"
          />
        </g>
        <rect
          x="130"
          y="48"
          width="64"
          height="9"
          rx="3"
          fill="#1E40AF"
          opacity="0.85"
        />
        <text
          x="162"
          y="54.5"
          textAnchor="middle"
          fill="rgba(255,255,255,0.85)"
          fontSize="4.5"
          fontFamily="monospace"
          fontWeight="600"
        >
          SOFTWARE ESTATE
        </text>
        <text
          x="162"
          y="76"
          textAnchor="middle"
          fill="#F1F5F9"
          fontSize="10"
          fontFamily="Plus Jakarta Sans, sans-serif"
          fontWeight="700"
        >
          Your System
        </text>
        <text
          x="162"
          y="90"
          textAnchor="middle"
          fill="#64748B"
          fontSize="5.5"
          fontFamily="Plus Jakarta Sans, sans-serif"
          fontStyle="italic"
        >
          the system in scope
        </text>
        <text
          x="162"
          y="108"
          textAnchor="middle"
          fill="#94A3B8"
          fontSize="5"
          fontFamily="monospace"
        >
          [Software System]
        </text>

        {/* System → External systems */}
        {externals.map((e, i) => (
          <line
            key={`le${i}`}
            x1="218"
            y1="80"
            x2={e.cx - 24}
            y2={e.cy}
            stroke="#3B82F6"
            strokeWidth="0.9"
            opacity="0.45"
            strokeDasharray="2.5,2"
            markerEnd="url(#arrow-blue)"
          />
        ))}

        {/* External system boxes */}
        {externals.map((e, i) => (
          <g key={`e${i}`}>
            <rect
              x={e.cx - 24}
              y={e.cy - 7}
              width={48}
              height={14}
              rx="3"
              fill="rgba(15,23,42,0.92)"
              stroke="#3B82F6"
              strokeWidth="0.8"
              opacity="0.85"
            />
            <rect
              x={e.cx - 22}
              y={e.cy - 5}
              width={16}
              height={10}
              rx="2"
              fill="#1E3A8A"
              opacity="0.85"
            />
            <text
              x={e.cx - 14}
              y={e.cy + 2.5}
              textAnchor="middle"
              fill="rgba(255,255,255,0.75)"
              fontSize="3.8"
              fontFamily="monospace"
              fontWeight="600"
            >
              {e.tag}
            </text>
            <text
              x={e.cx + 6}
              y={e.cy + 2.5}
              textAnchor="middle"
              fill="#94A3B8"
              fontSize="5.5"
              fontFamily="Plus Jakarta Sans, sans-serif"
              fontWeight="500"
            >
              {e.label}
            </text>
          </g>
        ))}

        {/* Footer label */}
        <rect
          x="100"
          y="144"
          width="120"
          height="12"
          rx="6"
          fill="rgba(30,41,59,0.8)"
        />
        <text
          x="160"
          y="152.5"
          textAnchor="middle"
          fill="#64748B"
          fontSize="6"
          fontFamily="Plus Jakarta Sans, sans-serif"
          fontWeight="500"
        >
          L1 · System Context
        </text>
      </svg>
    );
  }

  // ── L2: CONTAINER / SERVICE VIEW ─────────────────────────────────────────
  // Proper C4 L2: deployable containers inside the system — services AND
  // the data-tier (DB, cache, queue) — with the communication lines between
  // them. This is where Postgres / Redis / Kafka belong.
  if (type === "service") {
    const nodes = [
      {
        cx: 55,
        cy: 40,
        label: "api-gw",
        status: "active" as const,
        kind: "service" as const,
        tag: "SVC",
      },
      {
        cx: 160,
        cy: 40,
        label: "user-svc",
        status: "idle" as const,
        kind: "service" as const,
        tag: "SVC",
      },
      {
        cx: 265,
        cy: 40,
        label: "pay-svc",
        status: "idle" as const,
        kind: "service" as const,
        tag: "SVC",
      },
      {
        cx: 55,
        cy: 100,
        label: "Redis",
        status: "idle" as const,
        kind: "cache" as const,
        tag: "CACHE",
      },
      {
        cx: 160,
        cy: 100,
        label: "Postgres",
        status: "idle" as const,
        kind: "db" as const,
        tag: "DB",
      },
      {
        cx: 265,
        cy: 100,
        label: "Kafka",
        status: "idle" as const,
        kind: "queue" as const,
        tag: "QUEUE",
      },
    ];
    // service → service AND service → data-tier edges
    const edges = [
      [55, 40, 160, 40], // api-gw → user-svc
      [160, 40, 265, 40], // user-svc → pay-svc
      [55, 40, 55, 100], // api-gw → Redis
      [160, 40, 160, 100], // user-svc → Postgres
      [265, 40, 265, 100], // pay-svc → Kafka
      [265, 40, 160, 100], // pay-svc → Postgres
    ];

    const kindColor = (kind: string) => {
      if (kind === "db") return "#1D4ED8";
      if (kind === "cache") return "#0E7490";
      if (kind === "queue") return "#7C3AED";
      return "#14532D";
    };

    return (
      <svg viewBox="0 0 320 160" className="lp-mockup-svg" aria-hidden="true">
        {defs}
        <rect width="320" height="160" rx="12" fill="#08110a" />
        <rect width="320" height="160" rx="12" fill="url(#bg-glow-green)" />
        <rect width="320" height="160" rx="12" fill="url(#grid)" />
        <ellipse
          cx="160"
          cy="70"
          rx="100"
          ry="60"
          fill="#14532D"
          opacity="0.05"
        />

        {/* System boundary box (dashed) — signals "containers inside one system" */}
        <rect
          x="16"
          y="18"
          width="288"
          height="118"
          rx="8"
          fill="none"
          stroke="rgba(34,197,94,0.2)"
          strokeWidth="0.8"
          strokeDasharray="3,2.5"
        />
        <text
          x="26"
          y="28"
          fill="#4B5563"
          fontSize="5"
          fontFamily="monospace"
          letterSpacing="0.08em"
        >
          [SYSTEM: Your Software Estate]
        </text>

        {edges.map(([x1, y1, x2, y2], i) => (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#22C55E"
            strokeWidth="1.2"
            opacity="0.5"
            markerEnd="url(#arrow-green)"
          />
        ))}

        {nodes.map((node, i) => (
          <g key={i}>
            <rect
              x={node.cx - 24}
              y={node.cy - 16}
              width={48}
              height={32}
              rx="8"
              fill="#000"
              opacity="0.3"
              filter="url(#glow-green)"
            />
            <rect
              x={node.cx - 24}
              y={node.cy - 16}
              width={48}
              height={32}
              rx="8"
              fill={
                node.status === "active" ? "#0F172A" : "rgba(15,23,42,0.85)"
              }
              stroke={node.status === "active" ? "#4ADE80" : "#22C55E"}
              strokeWidth={node.status === "active" ? "1.5" : "0.8"}
              opacity={node.status === "active" ? 1 : 0.75}
              filter={node.status === "active" ? "url(#glow-green)" : undefined}
            />
            {/* Container-type badge */}
            <rect
              x={node.cx - 14}
              y={node.cy - 14}
              width={28}
              height={7}
              rx="2"
              fill={kindColor(node.kind)}
              opacity="0.85"
            />
            <text
              x={node.cx}
              y={node.cy - 9}
              textAnchor="middle"
              fill="rgba(255,255,255,0.85)"
              fontSize="3.6"
              fontFamily="monospace"
              fontWeight="700"
            >
              {node.tag}
            </text>
            {/* Label */}
            <text
              x={node.cx}
              y={node.cy + 4}
              textAnchor="middle"
              fill={node.status === "active" ? "#F1F5F9" : "#CBD5E1"}
              fontSize="6.5"
              fontFamily="monospace"
              fontWeight={node.status === "active" ? "600" : "500"}
            >
              {node.label}
            </text>
          </g>
        ))}

        <rect
          x="110"
          y="144"
          width="100"
          height="12"
          rx="6"
          fill="rgba(15,23,42,0.8)"
        />
        <text
          x="160"
          y="152.5"
          textAnchor="middle"
          fill="#4B5563"
          fontSize="6"
          fontFamily="Plus Jakarta Sans, sans-serif"
          fontWeight="500"
        >
          L2 · Container View
        </text>
      </svg>
    );
  }

  // ── L3: COMPONENT / INTERNALS VIEW ────────────────────────────────────────
  // Proper C4 L3: zoomed into ONE container (here: user-svc). Shows the
  // architectural components inside it, grouped by layer, with the call
  // flow (Controllers → Services → Repositories).
  const LAYER_Y = { controller: 38, service: 78, repo: 118 };
  const componentNodes: Array<{
    cx: number;
    label: string;
    layer: "controller" | "service" | "repo";
  }> = [
    // Controllers / Handlers
    { cx: 60, label: "AuthController", layer: "controller" },
    { cx: 135, label: "UserController", layer: "controller" },
    { cx: 210, label: "ProfileController", layer: "controller" },
    { cx: 285, label: "WebhookHandler", layer: "controller" },
    // Services / Business logic
    { cx: 60, label: "AuthService", layer: "service" },
    { cx: 135, label: "UserService", layer: "service" },
    { cx: 210, label: "ProfileService", layer: "service" },
    { cx: 285, label: "EventEmitter", layer: "service" },
    // Repositories / Data access
    { cx: 60, label: "SessionRepo", layer: "repo" },
    { cx: 135, label: "UserRepo", layer: "repo" },
    { cx: 210, label: "ProfileRepo", layer: "repo" },
    { cx: 285, label: "OutboxRepo", layer: "repo" },
  ];

  // Call-flow edges: vertical (layer to layer) + a couple of horizontal
  // peer calls to show component collaboration.
  const controllerToService = [60, 135, 210, 285].map(
    (cx) => [cx, 46, cx, 68] as const,
  );
  const serviceToRepo = [60, 135, 210, 285].map(
    (cx) => [cx, 86, cx, 108] as const,
  );
  const peerEdges = [
    [72, 78, 123, 78] as const, // AuthService → UserService
    [222, 78, 273, 78] as const, // ProfileService → EventEmitter
  ];

  const layerMeta = (layer: "controller" | "service" | "repo") => {
    if (layer === "controller")
      return {
        tag: "CTRL",
        fill: "rgba(67,56,202,0.25)",
        stroke: "#818CF8",
        accent: "#6366F1",
      };
    if (layer === "service")
      return {
        tag: "SVC",
        fill: "rgba(79,70,229,0.22)",
        stroke: "#6366F1",
        accent: "#4F46E5",
      };
    return {
      tag: "REPO",
      fill: "rgba(30,27,75,0.85)",
      stroke: "#4F46E5",
      accent: "#3730A3",
    };
  };

  return (
    <svg viewBox="0 0 320 160" className="lp-mockup-svg" aria-hidden="true">
      {defs}
      <rect width="320" height="160" rx="12" fill="#0c0c1e" />
      <rect width="320" height="160" rx="12" fill="url(#bg-glow-indigo)" />
      <rect width="320" height="160" rx="12" fill="url(#grid)" />
      <ellipse
        cx="160"
        cy="75"
        rx="110"
        ry="65"
        fill="#312E81"
        opacity="0.04"
      />

      {/* Container boundary — "we've zoomed into user-svc" */}
      <rect
        x="16"
        y="18"
        width="288"
        height="118"
        rx="8"
        fill="none"
        stroke="rgba(99,102,241,0.22)"
        strokeWidth="0.8"
        strokeDasharray="3,2.5"
      />
      <text
        x="26"
        y="28"
        fill="#6B7280"
        fontSize="5"
        fontFamily="monospace"
        letterSpacing="0.08em"
      >
        [CONTAINER: user-svc]
      </text>

      {/* Soft layer bands */}
      {(["controller", "service", "repo"] as const).map((layer) => (
        <rect
          key={`band-${layer}`}
          x="32"
          y={LAYER_Y[layer] - 14}
          width="258"
          height="28"
          rx="5"
          fill="rgba(99,102,241,0.04)"
          stroke="rgba(99,102,241,0.1)"
          strokeWidth="0.5"
        />
      ))}

      {/* Layer labels on the right */}
      {(
        [
          { layer: "controller", label: "Controllers" },
          { layer: "service", label: "Services" },
          { layer: "repo", label: "Repositories" },
        ] as const
      ).map((l) => (
        <text
          key={l.layer}
          x="302"
          y={LAYER_Y[l.layer] + 2}
          textAnchor="end"
          fill="#6B7280"
          fontSize="4.5"
          fontFamily="monospace"
          letterSpacing="0.05em"
          opacity="0.75"
        >
          {l.label.toUpperCase()}
        </text>
      ))}

      {/* Vertical call-flow edges: controller → service → repo */}
      {[...controllerToService, ...serviceToRepo].map(([x1, y1, x2, y2], i) => (
        <line
          key={`v${i}`}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="#818CF8"
          strokeWidth="0.9"
          opacity="0.5"
          markerEnd="url(#arrow-indigo)"
        />
      ))}

      {/* Peer component collaboration */}
      {peerEdges.map(([x1, y1, x2, y2], i) => (
        <line
          key={`p${i}`}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="#818CF8"
          strokeWidth="0.8"
          opacity="0.45"
          strokeDasharray="2.5,2"
          markerEnd="url(#arrow-indigo)"
        />
      ))}

      {componentNodes.map((node, i) => {
        const meta = layerMeta(node.layer);
        const cy = LAYER_Y[node.layer];
        return (
          <g key={`n${i}`}>
            <rect
              x={node.cx - 28}
              y={cy - 8}
              width={56}
              height={16}
              rx="4"
              fill="rgba(15,15,40,0.92)"
              stroke={meta.stroke}
              strokeWidth="0.9"
              opacity="0.92"
              filter="url(#shadow-node)"
            />
            {/* Layer tag */}
            <rect
              x={node.cx - 26}
              y={cy - 6}
              width={14}
              height={5.5}
              rx="1.2"
              fill={meta.accent}
              opacity="0.9"
            />
            <text
              x={node.cx - 19}
              y={cy - 2}
              textAnchor="middle"
              fill="rgba(255,255,255,0.9)"
              fontSize="3.4"
              fontFamily="monospace"
              fontWeight="700"
            >
              {meta.tag}
            </text>
            <text
              x={node.cx + 4}
              y={cy + 3}
              textAnchor="middle"
              fill="#C7D2FE"
              fontSize="4.6"
              fontFamily="monospace"
              fontWeight="500"
            >
              {node.label}
            </text>
          </g>
        );
      })}

      <rect
        x="108"
        y="144"
        width="104"
        height="12"
        rx="6"
        fill="rgba(15,15,40,0.8)"
      />
      <text
        x="160"
        y="152.5"
        textAnchor="middle"
        fill="#4B5563"
        fontSize="6"
        fontFamily="Plus Jakarta Sans, sans-serif"
        fontWeight="500"
      >
        L3 · Component View
      </text>
    </svg>
  );
};

const StageCard: React.FC<(typeof PLATFORM_STAGES)[number]> = ({
  number,
  name,
  tagline,
  description,
  icon,
  color,
}) => (
  <article className={`lp-stage-card lp-stage-card--${color}`}>
    <div className="lp-stage-card__header">
      <span className="lp-stage-card__number">{number}</span>
      <span className={`lp-stage-card__icon lp-stage-card__icon--${color}`}>
        {icon}
      </span>
    </div>
    <h3 className="lp-stage-card__name">{name}</h3>
    <p className="lp-stage-card__tagline">{tagline}</p>
    <p className="lp-stage-card__description">{description}</p>
  </article>
);

const PipelineStagesSection: React.FC = () => (
  <section className="lp-pipeline" aria-label="How the platform works">
    <div className="lp-section-header">
      <span className="lp-eyebrow">Three stages. One source of truth.</span>
      <h2>How the platform works.</h2>
      <p>
        What an ontology did for enterprise data — we are doing for enterprise
        software.
      </p>
    </div>
    <div className="lp-stages__grid">
      {PLATFORM_STAGES.map((stage) => (
        <StageCard key={stage.number} {...stage} />
      ))}
    </div>
  </section>
);

const RiskSection: React.FC = () => (
  <section className="lp-risks" aria-label="Risk metrics">
    <div className="lp-section-header">
      <span className="lp-eyebrow">The Intelligence</span>
      <h2>We turn architecture into a risk register.</h2>
      <p>
        Every node on the graph carries the four metrics that keep CIOs awake at
        night — continuously computed from your code, not gathered by quarterly
        survey.
      </p>
    </div>
    <div className="lp-risks__grid">
      {RISKS.map((risk) => (
        <article key={risk.title} className="lp-risk-card">
          <span className="lp-risk-card__icon">{risk.icon}</span>
          <h3>{risk.title}</h3>
          <span className="lp-risk-card__stat">{risk.stat}</span>
          <span className="lp-risk-card__caption">{risk.statCaption}</span>
          <p>{risk.description}</p>
          <span className="lp-risk-card__source">{risk.source}</span>
        </article>
      ))}
    </div>
  </section>
);

const TeamSection: React.FC = () => (
  <section className="lp-team" id="partners" aria-label="Founders">
    <div className="lp-section-header">
      <span className="lp-eyebrow">Team &amp; Ask</span>
      <h2>Built by engineers. Run from Vienna.</h2>
      <p>
        Where we are — and the doors we need opened. No consultants, no
        decks-first theatrics, just practitioners shipping against real
        codebases.
      </p>
    </div>

    {/* ── FOUNDING NARRATIVE ── */}
    <div className="lp-team__narrative">
      <p className="lp-team__narrative-lead">
        Stage: MVP. Extraction engine live across multi-language codebases.
      </p>
      <p className="lp-team__narrative-body">
        The product has two layers. A code extraction engine that needs to be
        precise, deterministic, and robust at scale — that&apos;s one domain. An
        intelligence layer on top that needs to be reliable, auditable, and
        production-grade — that&apos;s the other. We each built half the product
        before we formalised the company.
      </p>
      <p className="lp-team__narrative-body">
        We did not start with a pitch deck. We started with the extraction
        engine — it runs today, across multiple languages, on real repositories.
      </p>
    </div>

    <div className="lp-team__grid">
      {FOUNDERS.map((founder) => (
        <article key={founder.name} className="lp-founder-card">
          <div className="lp-founder-card__avatar">
            <GeometricAvatar initials={founder.initials} seed={founder.seed} />
          </div>
          <div className="lp-founder-card__info">
            <h3>{founder.name}</h3>
            <span className="lp-founder-card__title">{founder.title}</span>
            <p>{founder.bio}</p>
          </div>
          <MailTo
            encoded={founder.email}
            className="lp-btn lp-btn--primary lp-btn--pill lp-founder-card__cta"
          >
            <span>Email {founder.name.split(" ")[0]}</span>
            <ArrowRight size={14} />
          </MailTo>
        </article>
      ))}
    </div>

    {/* ── ASK BLOCK ── */}
    <div className="lp-ask-block">
      <h2>The Ask: 3 enterprise design partners.</h2>
      <p
        style={{
          fontStyle: "italic",
          opacity: 0.75,
          maxWidth: "640px",
          margin: "0 auto 1.5rem",
          textAlign: "center",
        }}
      >
        Ideal profile: 50+ services, platform engineering leadership, active
        modernization pressure.
      </p>
      <div className="lp-ask-block__perks">
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Free pilot deployment on one repo cluster</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Weekly co-development with both founders</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>First-partner pricing locked for 24 months</span>
        </div>
      </div>
      <div className="lp-ask-block__cta">
        <MailTo
          encoded="mnbpD@mbjbnhplb!dpnqpvBjmvh"
          className="lp-btn lp-btn--primary lp-btn--pill"
        >
          <span>Become a Design Partner</span>
          <ArrowRight size={16} />
        </MailTo>
      </div>
    </div>
  </section>
);

const Footer: React.FC = () => (
  <footer className="lp-footer" role="contentinfo">
    <div className="lp-footer__inner">
      <span>© 2026 KnowledgeForge. All rights reserved.</span>
      <div className="lp-footer__links">
        <MailTo encoded="mnbpD@mbjbnhplb!dpnqpvBjmvh">Contact</MailTo>
        <a href="/workspace">Product</a>
      </div>
    </div>
  </footer>
);

/* ─────────────────────────────────────────────────────────────────────────────
 * ROOT COMPONENT
 * ───────────────────────────────────────────────────────────────────────────── */

const LandingPage: React.FC = () => {
  return (
    <div className="lp-page">
      <Navbar />
      <main className="lp-main">
        {/* ── HERO ── */}
        <HeroSection />

        {/* ── THE STAKES ── */}
        <section className="lp-stakes" aria-label="The stakes">
          <div className="lp-stakes__header">
            <span className="lp-eyebrow">The Stakes</span>
            <h2>Architectural opacity is a P&amp;L problem.</h2>
            <p>
              Three numbers that every CIO already knows — and that a
              ground-truth map of the estate would directly move.
            </p>
          </div>
          <div className="lp-stakes__grid">
            {STATS.map((s) => (
              <StatCard key={s.value} {...s} />
            ))}
          </div>
        </section>

        {/* ── TWO AUDIENCES ── */}
        <section className="lp-audiences" aria-label="Two audiences">
          <div className="lp-section-header">
            <span className="lp-eyebrow">The Problem</span>
            <h2>Two audiences. Disconnected silos.</h2>
            <p>
              Engineering and leadership stare at the same estate — and see
              different fictions. Slow onboarding, duplicated work, coordination
              bottlenecks, and risk nobody owns.
            </p>
          </div>
          <div className="lp-audiences__grid">
            <BlindSpotCard
              title="The Operator’s Blind Spot"
              subtitle="Engineering"
              accent="blue"
              painPoints={OPERATOR_PAIN_POINTS}
            />
            <BlindSpotCard
              title="The Commander’s Blind Spot"
              subtitle="Leadership"
              accent="slate"
              painPoints={COMMANDER_PAIN_POINTS}
            />
          </div>
        </section>

        {/* ── MARKET GAP ── */}
        <section className="lp-market" aria-label="Market gap">
          <div className="lp-section-header">
            <span className="lp-eyebrow">The Market Gap</span>
            <h2>The map always lags the code.</h2>
            <p>
              Three tool categories. Three flavors of the same failure. The
              market has mapped the symptom — nobody has mapped the source code.
            </p>
          </div>
          <div className="lp-market__table">
            <div className="lp-market__row lp-market__row--header">
              <span>Tool Category</span>
              <span>Examples</span>
              <span>Why It Fails</span>
            </div>
            {[
              [
                "Diagram Tools",
                "Structurizr, IcePanel",
                "Drawn by hand. Go stale fast. Abandoned within a quarter.",
              ],
              [
                "Developer Portals",
                "Backstage, Port",
                "Service lists, not architecture. Maintained manually.",
              ],
              [
                "EA Platforms",
                "SAP LeanIX, Ardoq",
                "Built for executives. Disconnected from code.",
              ],
            ].map(([cat, examples, fail]) => (
              <div key={cat} className="lp-market__row">
                <span className="lp-market__cat">{cat}</span>
                <span className="lp-market__examples">{examples}</span>
                <span className="lp-market__fail">{fail}</span>
              </div>
            ))}
          </div>

          {/* ── POSITIONING MATRIX ── */}
          <div className="lp-section-header lp-section-header--tight">
            <span className="lp-eyebrow">Positioning</span>
            <h2>Nobody sits where we sit.</h2>
            <p>
              The capabilities the enterprise needs — versus what the market
              actually delivers.
            </p>
          </div>
          <div className="lp-market__table">
            <div className="lp-market__matrix-row lp-market__matrix-row--header">
              <span>Capability</span>
              <span>Diagram Tools</span>
              <span>Dev Portals</span>
              <span>EA Platforms</span>
              <span>KnowledgeForge</span>
            </div>
            {[
              ["Auto-extracts from source code", "—", "~", "—", "✓"],
              ["Updates in real time with commits", "—", "~", "—", "✓"],
              ["Serves developers AND executives", "—", "—", "—", "✓"],
              ["Graph-native (relationships first)", "—", "—", "~", "✓"],
              ["Risk metrics overlaid on architecture", "—", "—", "~", "✓"],
              ["C4-compliant ontology", "~", "—", "—", "✓"],
            ].map(([capability, diag, dev, ea, kf]) => (
              <div key={capability} className="lp-market__matrix-row">
                <span className="lp-market__cat">{capability}</span>
                <span className="lp-market__matrix-cell">
                  {diag === "✓" ? (
                    <CheckCircle2 size={18} color="#22C55E" />
                  ) : diag === "~" ? (
                    <span style={{ color: "#F59E0B" }}>Partial</span>
                  ) : (
                    <XCircle size={18} style={{ opacity: 0.35 }} />
                  )}
                </span>
                <span className="lp-market__matrix-cell">
                  {dev === "✓" ? (
                    <CheckCircle2 size={18} color="#22C55E" />
                  ) : dev === "~" ? (
                    <span style={{ color: "#F59E0B" }}>Partial</span>
                  ) : (
                    <XCircle size={18} style={{ opacity: 0.35 }} />
                  )}
                </span>
                <span className="lp-market__matrix-cell">
                  {ea === "✓" ? (
                    <CheckCircle2 size={18} color="#22C55E" />
                  ) : ea === "~" ? (
                    <span style={{ color: "#F59E0B" }}>Partial</span>
                  ) : (
                    <XCircle size={18} style={{ opacity: 0.35 }} />
                  )}
                </span>
                <span className="lp-market__matrix-cell lp-market__matrix-cell--strong">
                  {kf === "✓" ? <CheckCircle2 size={20} color="#22C55E" /> : kf}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ── SOLUTION ── */}
        <section className="lp-solution" id="solution" aria-label="Solution">
          <div className="lp-section-header">
            <span className="lp-eyebrow">The Solution</span>
            <h2>The map lives inside the code itself.</h2>
            <p>
              We read your repositories directly and build an accurate graph of
              everything that runs — self-updating with every commit, queryable
              in plain English, and rendered as one source of truth for
              developers and leadership alike.
            </p>
          </div>
          <div className="lp-pillars__grid">
            {PILLARS.map((p) => (
              <PillarCard key={p.title} {...p} />
            ))}
          </div>
        </section>

        {/* ── THREE ALTITUDES ── */}
        <section className="lp-altitudes" aria-label="Product views">
          <div className="lp-section-header">
            <span className="lp-eyebrow">The Ontology</span>
            <h2>Zoom out for strategy. Zoom in for engineering.</h2>
            <p>
              What ontologies did for enterprise data, KnowledgeForge does for
              enterprise software. Three layers, one graph — generated
              automatically from your code.
            </p>
          </div>
          <AltitudeTabSwitcher />
        </section>

        {/* ── THREE-STAGE PLATFORM ── */}
        <PipelineStagesSection />

        {/* ── RISK REGISTER ── */}
        <RiskSection />

        {/* ── TEAM + CTA ── */}
        <TeamSection />
      </main>
      <Footer />
    </div>
  );
};

export default LandingPage;
