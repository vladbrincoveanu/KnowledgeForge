import React, { useMemo, useState } from "react";
import {
  AlarmClock,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  CheckCircle2,
  Code2,
  Database,
  Download,
  Eye,
  FileText,
  GitBranch,
  Globe,
  HardDrive,
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
    value: "30%",
    label: "IT Budget Waste",
    detail:
      "Capital wasted on misaligned projects due to structural failure of visibility.",
    source: "Source: PMI",
  },
  {
    value: "$6T",
    label: "Global Tech Debt",
    detail:
      "The cost of legacy debt has doubled since 2012, stifling enterprise agility.",
    source: "Source: Protiviti",
  },
  {
    value: "$4.88M",
    label: "Per Data Breach",
    detail:
      "Average breach cost; supply-chain risks unmanageable without a dependency map.",
    source: "Source: IBM",
  },
];

const OPERATOR_PAIN_POINTS = [
  {
    icon: <AlertTriangle size={16} />,
    text: '"What breaks if I change this service?"',
  },
  {
    icon: <Eye size={16} />,
    text: "Developers cannot see downstream dependencies across distributed repos.",
  },
  {
    icon: <AlarmClock size={16} />,
    text: "Onboarding cycles drag from days into months.",
  },
  {
    icon: <Link2 size={16} />,
    text: "Duplicated services built by teams with no visibility into each other.",
  },
];

const COMMANDER_PAIN_POINTS = [
  {
    icon: <Users2 size={16} />,
    text: '"What does our engineering org actually run?"',
  },
  {
    icon: <Network size={16} />,
    text: "M&A integrations rely on guesswork for system and vendor redundancy.",
  },
  {
    icon: <ShieldAlert size={16} />,
    text: "Vulnerabilities triaged without knowing true business blast radius.",
  },
  {
    icon: <MessageCircle size={16} />,
    text: "Strategic decisions rely on 'Tribal Knowledge' instead of data.",
  },
];

const PILLARS = [
  {
    icon: <FileText size={20} />,
    title: "No Manual Diagrams",
    description:
      "Eliminate outdated wikis and hand-maintained catalogs. Truth lives in the code.",
  },
  {
    icon: <RefreshCw size={20} />,
    title: "Self-Updating",
    description:
      "The map evolves automatically with every commit, Pull Request, and redeploy.",
  },
  {
    icon: <MessageCircle size={20} />,
    title: "Quarriable Altitudes",
    description:
      "Leverage LLMs to explore complex data and extract insights using natural language.",
  },
  {
    icon: <Boxes size={20} />,
    title: "One Source of Truth",
    description:
      "Developers see the system, leadership sees the portfolio — same deterministic data.",
  },
];

const ALTITUDES = [
  {
    level: "L1",
    name: "Ecosystem View",
    persona: "CIO / Board",
    description:
      "Your software in context. Focus on business capabilities and regulatory exposure rather than repository names. Identify external integrations and vendor risks that threaten compliance and continuity.",
    mockup: "context",
  },
  {
    level: "L2",
    name: "Service View",
    persona: "Architect / Tech Lead",
    description:
      "The major moving parts. Map interaction between microservices, containers, and databases. Enable blast-radius simulation for proposed changes before architectural drift compromises integrity.",
    mockup: "service",
  },
  {
    level: "L3",
    name: "Internals View",
    persona: "Developer / SRE",
    description:
      "The real building blocks. Gain immediate clarity on classes, functions, and execution paths. Reduce engineer onboarding from months to hours with deep links back to Git.",
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
    stat: "23–25% Turnover",
    description:
      "Betweenness centrality exposes engineers who own critical paths. Know exactly who needs cross-training before departure creates an operational vacuum.",
  },
  {
    icon: <Link2 size={20} />,
    title: "Supply-Chain Risk",
    stat: "$4.88M Per Breach",
    description:
      "When a CVE drops, trace its lineage through the graph to the exact business systems exposed — immediate triage context.",
  },
  {
    icon: <AlertTriangle size={20} />,
    title: "Technical Debt",
    stat: "30% IT Budget Waste",
    description:
      "Identify true architectural debt — coupling patterns and bottlenecks that actually throttle deployment velocity.",
  },
  {
    icon: <Boxes size={20} />,
    title: "Lifecycle Waste",
    stat: "3–5× M&A Redundancy",
    description:
      "Expose duplicate billing, auth, and CRM stacks in post-acquisition portfolios. Show leadership what's safe to decommission.",
  },
];

const FOUNDERS = [
  {
    initials: "IR",
    name: "Iulia Rinea",
    title: "Co-founder",
    bio: "Data & AI Platform Engineer at AI Factory Austria. Expert in production ML infrastructure and ingestion pipelines.",
    email: "rineaiulia17@gmail.com",
    seed: 42,
  },
  {
    initials: "VB",
    name: "Vlad Brincoveanu",
    title: "Co-founder",
    bio: "Software Engineer at CID. Expert in distributed systems, code-graph tooling, and Kafka infrastructure.",
    email: "ggvladbrincoveanu@gmail.com",
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
        <a
          href="mailto:ggvladbrincoveanu@gmail.com"
          className="lp-btn lp-btn--ghost"
        >
          Contact Sales
        </a>
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
        <h1>The operating system for your software estate.</h1>
        <p className="lp-hero__lede">
          From code commit to boardroom. KnowledgeForge treats source code as
          the ultimate authority — eliminating documentation debt and turning
          architectural opacity into a data-driven command center.
        </p>
        <div className="lp-hero__actions">
          <a href="#partners" className="lp-btn lp-btn--primary lp-btn--pill">
            <span>Request Pilot Access</span>
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
            No credit card. Start with the architecture evidence you already
            have.
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

  // ── L1: CONTEXT / ECOSYSTEM ───────────────────────────────────────────────
  if (type === "context") {
    const nodes = [
      { cx: 60, cy: 50, label: "Auth", active: false, badge: "svc" },
      { cx: 160, cy: 30, label: "API Gateway", active: true, badge: "svc" },
      { cx: 260, cy: 55, label: "Postgres", active: false, badge: "db" },
      { cx: 100, cy: 110, label: "Kafka", active: false, badge: "queue" },
      { cx: 220, cy: 105, label: "Redis", active: false, badge: "cache" },
    ];
    const edges = [
      [60, 50, 160, 30],
      [160, 30, 260, 55],
      [100, 110, 60, 50],
      [220, 105, 160, 30],
      [100, 110, 220, 105],
    ];
    return (
      <svg viewBox="0 0 320 160" className="lp-mockup-svg" aria-hidden="true">
        {defs}
        {/* Background */}
        <rect width="320" height="160" rx="12" fill="#0a0f1e" />
        <rect width="320" height="160" rx="12" fill="url(#bg-glow-blue)" />
        <rect width="320" height="160" rx="12" fill="url(#grid)" />

        {/* Ambient glow */}
        <ellipse
          cx="160"
          cy="70"
          rx="100"
          ry="60"
          fill="#1D4ED8"
          opacity="0.05"
        />

        {/* Edges */}
        {edges.map(([x1, y1, x2, y2], i) => (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#3B82F6"
            strokeWidth="1.5"
            opacity="0.5"
            markerEnd="url(#arrow-blue)"
          />
        ))}

        {/* Nodes */}
        {nodes.map((node, i) => (
          <g key={i} filter="url(#shadow-node)">
            {/* Glow halo */}
            <rect
              x={node.cx - 28}
              y={node.cy - 20}
              width={56}
              height={40}
              rx="10"
              fill="#3B82F6"
              opacity={node.active ? "0.2" : "0.06"}
              filter="url(#glow-blue)"
            />
            {/* Card body */}
            <rect
              x={node.cx - 26}
              y={node.cy - 18}
              width={52}
              height={36}
              rx="8"
              fill={node.active ? "#1E293B" : "rgba(15,23,42,0.9)"}
              stroke={node.active ? "#60A5FA" : "#3B82F6"}
              strokeWidth={node.active ? "1.5" : "1"}
              opacity={node.active ? 1 : 0.75}
            />
            {/* Badge */}
            <rect
              x={node.cx - 10}
              y={node.cy - 16}
              width={20}
              height={8}
              rx="3"
              fill={
                node.badge === "db"
                  ? "#1D4ED8"
                  : node.badge === "queue"
                    ? "#7C3AED"
                    : "#1E40AF"
              }
              opacity="0.8"
            />
            <text
              x={node.cx}
              y={node.cy - 10}
              textAnchor="middle"
              fill="rgba(255,255,255,0.7)"
              fontSize="4.5"
              fontFamily="monospace"
              fontWeight="600"
            >
              {node.badge?.toUpperCase()}
            </text>
            {/* Label */}
            <text
              x={node.cx}
              y={node.cy + 5}
              textAnchor="middle"
              fill={node.active ? "#F1F5F9" : "#94A3B8"}
              fontSize="7"
              fontFamily="Plus Jakarta Sans, sans-serif"
              fontWeight={node.active ? "600" : "400"}
            >
              {node.label}
            </text>
          </g>
        ))}

        {/* Footer label */}
        <rect
          x="110"
          y="144"
          width="100"
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
          L1 · Ecosystem View
        </text>
      </svg>
    );
  }

  // ── L2: SERVICE VIEW ─────────────────────────────────────────────────────
  if (type === "service") {
    const nodes = [
      { cx: 80, cy: 40, label: "api-gw", status: "active" },
      { cx: 160, cy: 40, label: "user-svc", status: "idle" },
      { cx: 240, cy: 40, label: "pay-svc", status: "idle" },
      { cx: 80, cy: 100, label: "notif", status: "idle" },
      { cx: 160, cy: 100, label: "search", status: "idle" },
      { cx: 240, cy: 100, label: "notify", status: "idle" },
    ];
    const edges = [
      [80, 40, 160, 40],
      [160, 40, 240, 40],
      [80, 100, 80, 40],
      [80, 100, 160, 100],
      [160, 100, 240, 100],
      [160, 40, 160, 100],
    ];
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

        {edges.map(([x1, y1, x2, y2], i) => (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#22C55E"
            strokeWidth="1.4"
            opacity="0.55"
            markerEnd="url(#arrow-green)"
          />
        ))}

        {nodes.map((node, i) => (
          <g key={i}>
            {/* Shadow */}
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
            {/* Card */}
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
              opacity={node.status === "active" ? 1 : 0.65}
              filter={node.status === "active" ? "url(#glow-green)" : undefined}
            />
            {/* Status dot */}
            <circle
              cx={node.cx - 16}
              cy={node.cy - 9}
              r="2.5"
              fill={node.status === "active" ? "#4ADE80" : "#22C55E"}
              opacity={node.status === "active" ? 1 : 0.5}
            />
            {/* Label */}
            <text
              x={node.cx}
              y={node.cy + 5}
              textAnchor="middle"
              fill={node.status === "active" ? "#F1F5F9" : "#94A3B8"}
              fontSize="6.5"
              fontFamily="monospace"
              fontWeight={node.status === "active" ? "600" : "400"}
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
          L2 · Service View
        </text>
      </svg>
    );
  }

  // ── L3: CODE INTERNALS ────────────────────────────────────────────────────
  const codeNodes = [
    { cx: 50, cy: 35, label: "main.rs", kind: "file" },
    { cx: 115, cy: 35, label: "auth.rs", kind: "file" },
    { cx: 180, cy: 35, label: "db.rs", kind: "file" },
    { cx: 245, cy: 35, label: "mod.rs", kind: "file" },
    { cx: 50, cy: 72, label: "handler", kind: "mod" },
    { cx: 115, cy: 72, label: "model", kind: "mod" },
    { cx: 180, cy: 72, label: "repo", kind: "mod" },
    { cx: 245, cy: 72, label: "cache", kind: "mod" },
    { cx: 50, cy: 109, label: "tests.rs", kind: "file" },
    { cx: 115, cy: 109, label: "bench.rs", kind: "file" },
    { cx: 180, cy: 109, label: "util.rs", kind: "file" },
    { cx: 245, cy: 109, label: "error.rs", kind: "file" },
  ];
  const codeEdges = [
    [50, 41, 50, 63],
    [115, 41, 115, 63],
    [180, 41, 180, 63],
    [245, 41, 245, 63],
    [50, 80, 50, 100],
    [115, 80, 115, 100],
    [180, 80, 180, 100],
    [245, 80, 245, 100],
    [82, 72, 98, 72],
    [147, 72, 163, 72],
    [212, 72, 228, 72],
  ];
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

      {/* Connecting lines between modules */}
      {codeEdges.map(([x1, y1, x2, y2], i) => (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="#6366F1"
          strokeWidth="0.7"
          opacity="0.3"
          strokeDasharray="2,2"
        />
      ))}

      {/* Module row highlight */}
      <rect
        x="40"
        y="55"
        width="215"
        height="40"
        rx="6"
        fill="rgba(99,102,241,0.04)"
        stroke="rgba(99,102,241,0.1)"
        strokeWidth="0.5"
      />

      {codeNodes.map((node, i) => {
        const isFile = node.kind === "file";
        const fillColor = isFile ? "rgba(15,23,42,0.92)" : "rgba(30,27,75,0.9)";
        const strokeColor = isFile ? "#6366F1" : "#4F46E5";
        return (
          <g key={i}>
            <rect
              x={node.cx - 18}
              y={node.cy - 10}
              width={36}
              height={20}
              rx="4"
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth="0.8"
              opacity="0.8"
              filter="url(#shadow-node)"
            />
            {/* File/module icon indicator */}
            <rect
              x={node.cx - 16}
              y={node.cy - 8}
              width={6}
              height={7}
              rx="1.5"
              fill={strokeColor}
              opacity="0.4"
            />
            <text
              x={node.cx + 2}
              y={node.cy + 3}
              textAnchor="middle"
              fill="#C7D2FE"
              fontSize="5"
              fontFamily="monospace"
            >
              {node.label}
            </text>
          </g>
        );
      })}

      <rect
        x="110"
        y="144"
        width="100"
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
        L3 · Internals View
      </text>
    </svg>
  );
};

const PipelineSection: React.FC = () => (
  <section className="lp-pipeline" id="engine" aria-label="How it works">
    <div className="lp-section-header">
      <span className="lp-eyebrow">The Engine</span>
      <h2>From commit to intelligence.</h2>
      <p>
        A deterministic, five-stage pipeline. Unlike guesswork AI models, our
        process relies on mechanical precision — establishing trust through
        technical accuracy across every estate.
      </p>
    </div>
    <div className="lp-pipeline__steps">
      {PIPELINE_STEPS.map((step, i) => (
        <div key={step.number} className="lp-pipeline__step">
          {i > 0 && (
            <div className="lp-pipeline__arrow" aria-hidden="true">
              <ArrowRight size={14} />
            </div>
          )}
          <div className="lp-pipeline__item">
            <span className="lp-pipeline__badge">{step.number}</span>
            <div className="lp-pipeline__icon">{step.icon}</div>
            <h3>{step.name}</h3>
            <p>{step.description}</p>
          </div>
        </div>
      ))}
    </div>
  </section>
);

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
      <span className="lp-eyebrow">Risk Register</span>
      <h2>Board-level metrics. Real-time.</h2>
      <p>
        Every node on the graph carries the metrics that keep CIOs awake. We
        transform your architecture into a real-time risk register that
        prioritizes action over alert fatigue.
      </p>
    </div>
    <div className="lp-risks__grid">
      {RISKS.map((risk) => (
        <article key={risk.title} className="lp-risk-card">
          <span className="lp-risk-card__icon">{risk.icon}</span>
          <h3>{risk.title}</h3>
          <span className="lp-risk-card__stat">{risk.stat}</span>
          <p>{risk.description}</p>
        </article>
      ))}
    </div>
  </section>
);

const TeamSection: React.FC = () => (
  <section className="lp-team" id="partners" aria-label="Founders">
    <div className="lp-section-header">
      <span className="lp-eyebrow">The Team</span>
      <h2>Built by engineers who've lived this.</h2>
      <p>
        We understand the modernization pressure facing platform leaders because
        we have lived it. No consultants — just practitioners.
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
          <a
            href={`mailto:${founder.email}`}
            className="lp-btn lp-btn--primary lp-btn--pill lp-founder-card__cta"
          >
            <span>Email {founder.name.split(" ")[0]}</span>
            <ArrowRight size={14} />
          </a>
        </article>
      ))}
    </div>

    <div className="lp-ask-block">
      <h2>Seeking 3 Enterprise Design Partners</h2>
      <div className="lp-ask-block__perks">
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Free pilot deployment for one repository cluster</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>Weekly co-development with founders</span>
        </div>
        <div className="lp-perk">
          <CheckCircle2 size={16} />
          <span>First-partner pricing locked for 24 months</span>
        </div>
      </div>
      <div className="lp-ask-block__cta">
        <a href="#partners" className="lp-btn lp-btn--primary lp-btn--pill">
          <span>Request Pilot Access</span>
          <ArrowRight size={16} />
        </a>
      </div>
    </div>
  </section>
);

const Footer: React.FC = () => (
  <footer className="lp-footer" role="contentinfo">
    <div className="lp-footer__inner">
      <span>© 2026 KnowledgeForge. All rights reserved.</span>
      <div className="lp-footer__links">
        <a href="mailto:ggvladbrincoveanu@gmail.com">Contact</a>
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
            <h2>Quantifying the architectural void.</h2>
            <p>
              In the modern enterprise, architectural opacity is not a technical
              inconvenience — it is a board-level financial liability.
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
            <h2>A broken system of record.</h2>
            <p>
              This lack of a ground-truth map creates dual blind spots that
              paralyze both the execution and the strategy of the software
              estate.
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
            <span className="lp-eyebrow">Why Traditional Maps Fail</span>
            <h2>The market gap we close.</h2>
          </div>
          <div className="lp-market__table">
            <div className="lp-market__row lp-market__row--header">
              <span>Tool Category</span>
              <span>Examples</span>
              <span>Why It Fails</span>
            </div>
            {[
              [
                "Diagramming Tools",
                "Structurizr, IcePanel",
                "Diagrams go stale: Drawn by hand, accurate only on day one. Abandoned within a quarter.",
              ],
              [
                "Developer Portals",
                "Backstage, Port",
                "Portals lack system interaction: Excellent for ownership lists, zero signal on data flow or dependencies.",
              ],
              [
                "EA Platforms",
                "SAP LeanIX, Ardoq",
                "EA is disconnected from code: Built for board memos and maintained by manual Jira updates.",
              ],
            ].map(([cat, examples, fail]) => (
              <div key={cat} className="lp-market__row">
                <span className="lp-market__cat">{cat}</span>
                <span className="lp-market__examples">{examples}</span>
                <span className="lp-market__fail">{fail}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── SOLUTION ── */}
        <section className="lp-solution" id="solution" aria-label="Solution">
          <div className="lp-section-header">
            <span className="lp-eyebrow">The Solution</span>
            <h2>A living map of truth.</h2>
            <p>
              KnowledgeForge turns source code into a living map. By treating
              code as the ultimate authority, we eliminate documentation
              homework and build a Living Ontology that reflects the system as
              it truly exists.
            </p>
          </div>
          <div className="lp-pillars__grid">
            {PILLARS.map((p) => PillarCard(p))}
          </div>
        </section>

        {/* ── THREE ALTITUDES ── */}
        <section className="lp-altitudes" aria-label="Product views">
          <div className="lp-section-header">
            <span className="lp-eyebrow">Product Intelligence</span>
            <h2>Three altitudes of visibility.</h2>
            <p>
              Effective estate management requires altitude-based navigation.
              KnowledgeForge provides three distinct views from a single graph —
              seamlessly zoom between strategic and technical layers.
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
