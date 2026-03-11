import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Clock3,
  Euro,
  FileText,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Users2,
} from 'lucide-react';
import './LandingPage.scss';

/**
 * Hero metric displayed near the opening value proposition.
 */
interface HeroStat {
  value: string;
  label: string;
  detail: string;
}

/**
 * Product capability card rendered in the MVP section.
 */
interface CapabilityCard {
  icon: React.ReactElement;
  eyebrow: string;
  title: string;
  description: string;
}

/**
 * Launch step describing the staged MVP rollout.
 */
interface LaunchStep {
  week: string;
  title: string;
  description: string;
}

/**
 * Go-to-market card shown in the acquisition section.
 */
interface GtmCard {
  title: string;
  description: string;
  accent: string;
}

const heroStats: HeroStat[] = [
  {
    value: '5 min',
    label: 'to a board-ready narrative',
    detail: 'Translate uptime, security and cost signals into one plain-English summary.',
  },
  {
    value: '£2.4m',
    label: 'example annualized risk exposure',
    detail: 'Show the downside of delay in the same language the board already uses.',
  },
  {
    value: '3 pilots',
    label: 'priced for early design partners',
    detail: 'Start with focused mid-market teams at €500 per month and tune from real feedback.',
  },
];

const capabilityCards: CapabilityCard[] = [
  {
    icon: <ShieldAlert size={20} />,
    eyebrow: 'Input',
    title: 'Bring in the signals your team already has',
    description:
      'Uptime, security posture, estate costs and repository evidence become one shared risk baseline.',
  },
  {
    icon: <BarChart3 size={20} />,
    eyebrow: 'Output',
    title: 'Turn technical noise into a board risk score',
    description:
      'Quantify exposure in £ or € and package it with a concise summary executives can use immediately.',
  },
  {
    icon: <TrendingUp size={20} />,
    eyebrow: 'Benchmarking',
    title: 'Explain whether the number is normal or dangerous',
    description:
      'Compare posture against peers so the board sees what needs investment and what is already efficient.',
  },
];

const launchSteps: LaunchStep[] = [
  {
    week: 'Week 1',
    title: 'Ship the landing page and free score CTA',
    description:
      'Lead with board-language positioning, an instant risk snapshot and a no-credit-card start.',
  },
  {
    week: 'Weeks 2-4',
    title: 'Launch the MVP scoring workflow',
    description:
      'Ingest IT metrics, compute the risk number and generate a plain-English board summary.',
  },
  {
    week: 'Go-to-market',
    title: 'Target recently funded mid-market operators',
    description:
      'Sell into teams with budget, scrutiny and pressure to justify spend to investors or PE boards.',
  },
  {
    week: 'First revenue',
    title: 'Convert three design-partner pilots',
    description:
      'Use early pilots at €500 per month to tighten the score, the summary and the pricing story.',
  },
];

const gtmCards: GtmCard[] = [
  {
    title: 'Lead Magnet',
    description:
      'Package a short PDF on how to justify the 2026 IT budget to the board using risk, not jargon.',
    accent: 'Board-ready PDF for outbound and LinkedIn follow-up.',
  },
  {
    title: 'Ideal Buyer',
    description:
      'Recently funded mid-market companies with lean IT teams, board pressure and clear budget ownership.',
    accent: 'They can buy quickly and need a stronger story fast.',
  },
  {
    title: 'Pilot Offer',
    description:
      'Three hands-on pilots at €500 per month with close iteration on benchmarks, summary tone and packaging.',
    accent: 'Fast feedback loop before expanding pricing.',
  },
];

/**
 * Board-facing marketing landing page for KnowledgeForge.
 */
const LandingPage: React.FC = () => {
  return (
    <div className="landing-page">
      <section className="landing-hero">
        <div className="landing-hero__copy">
          <span className="landing-eyebrow">Board-ready IT risk intelligence</span>
          <h1>Stop justifying IT spend to the board. Show them the £ risk.</h1>
          <p className="landing-hero__lede">
            One dashboard. Plain English. Board-ready in 5 minutes.
          </p>
          <div className="landing-hero__actions">
            <Link to="/workspace" className="landing-button landing-button--primary">
              <span>See your IT risk score — free</span>
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/code-architecture"
              className="landing-button landing-button--secondary"
            >
              Explore the product
            </Link>
          </div>
          <div className="landing-hero__note">
            <CheckCircle2 size={18} />
            <span>No credit card. Start with the metrics and architecture evidence you already have.</span>
          </div>
        </div>

        <div className="landing-board-card">
          <div className="landing-board-card__header">
            <div>
              <span className="landing-board-card__label">Board risk snapshot</span>
              <h2>KnowledgeForge Risk Signal</h2>
            </div>
            <span className="landing-board-card__badge">
              <Sparkles size={14} />
              Plain English
            </span>
          </div>

          <div className="landing-board-card__score">
            <div>
              <span className="landing-board-card__score-label">Estimated annual exposure</span>
              <strong>£2.4m</strong>
            </div>
            <div className="landing-board-card__trend">
              <TrendingUp size={18} />
              <span>12% above peer benchmark</span>
            </div>
          </div>

          <div className="landing-board-card__summary">
            <p>Board summary</p>
            <blockquote>
              Security debt and settlement fragility now outweigh planned savings. Rebalance
              spend toward resilience before the next budgeting cycle.
            </blockquote>
          </div>

          <ul className="landing-board-card__signals">
            <li>
              <ShieldAlert size={16} />
              <span>Security controls lag peer median by 18%</span>
            </li>
            <li>
              <BarChart3 size={16} />
              <span>Core service uptime is stable, but incident recovery cost remains high</span>
            </li>
            <li>
              <FileText size={16} />
              <span>Board pack generated with benchmark context and spend recommendation</span>
            </li>
          </ul>
        </div>
      </section>

      <section className="landing-stats" aria-label="KnowledgeForge highlights">
        {heroStats.map(stat => (
          <article key={stat.label} className="landing-stat-card">
            <span className="landing-stat-card__value">{stat.value}</span>
            <h2>{stat.label}</h2>
            <p>{stat.detail}</p>
          </article>
        ))}
      </section>

      <section className="landing-section">
        <div className="landing-section__heading">
          <span className="landing-section__eyebrow">What ships in the MVP</span>
          <h2>Give the board a number, the story behind it and the benchmark around it.</h2>
          <p>
            The first release focuses on a narrow promise: turn IT metrics into one credible risk
            score with enough context to support a budget conversation.
          </p>
        </div>

        <div className="landing-card-grid">
          {capabilityCards.map(card => (
            <article key={card.title} className="landing-feature-card">
              <div className="landing-feature-card__icon">{card.icon}</div>
              <span className="landing-feature-card__eyebrow">{card.eyebrow}</span>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-section--split" id="mvp-plan">
        <div className="landing-plan-card">
          <span className="landing-section__eyebrow">Delivery plan</span>
          <h2>Four weeks to the first board conversation.</h2>
          <div className="landing-timeline">
            {launchSteps.map(step => (
              <article key={step.title} className="landing-timeline__item">
                <span className="landing-timeline__week">{step.week}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="landing-summary-panel">
          <div className="landing-summary-panel__header">
            <span className="landing-section__eyebrow">Board pack preview</span>
            <h2>What the CFO sees</h2>
          </div>
          <div className="landing-summary-panel__row">
            <div>
              <p>Risk score</p>
              <strong>74 / 100</strong>
            </div>
            <div>
              <p>Budget ask protected</p>
              <strong>£620k</strong>
            </div>
          </div>
          <div className="landing-summary-panel__copy">
            <p>
              “Current resilience investments cover only the most visible incidents. Without a
              targeted uplift in security controls and recovery capability, expected downside
              remains materially above peers.”
            </p>
          </div>
          <div className="landing-summary-panel__benchmarks">
            <div className="landing-benchmark">
              <span>Resilience</span>
              <div>
                <i style={{ width: '72%' }} />
              </div>
            </div>
            <div className="landing-benchmark">
              <span>Security</span>
              <div>
                <i style={{ width: '58%' }} />
              </div>
            </div>
            <div className="landing-benchmark">
              <span>Cost efficiency</span>
              <div>
                <i style={{ width: '81%' }} />
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="landing-section landing-section--accent">
        <div className="landing-section__heading">
          <span className="landing-section__eyebrow">Go to market</span>
          <h2>Start with teams that need a stronger board story right now.</h2>
        </div>

        <div className="landing-card-grid landing-card-grid--gtm">
          {gtmCards.map(card => (
            <article key={card.title} className="landing-gtm-card">
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <span>{card.accent}</span>
            </article>
          ))}
        </div>

        <div className="landing-audience-strip">
          <div>
            <Building2 size={18} />
            <span>Mid-market operators under PE or investor scrutiny</span>
          </div>
          <div>
            <Users2 size={18} />
            <span>IT leaders who need board-level language, not technical charts</span>
          </div>
          <div>
            <Clock3 size={18} />
            <span>Fast proof of value with a five-minute narrative, not a six-week rollout</span>
          </div>
          <div>
            <Euro size={18} />
            <span>Early pilots priced to learn quickly before scaling beyond €500 per month</span>
          </div>
        </div>
      </section>

      <section className="landing-cta-panel" id="pilot-access">
        <div>
          <span className="landing-section__eyebrow">Pilot access</span>
          <h2>Get the first board-ready score before the budget meeting gets harder.</h2>
          <p>
            Start with a free assessment, then convert the strongest design partners into the
            first paid pilots.
          </p>
        </div>
        <div className="landing-cta-panel__actions">
          <Link to="/workspace" className="landing-button landing-button--primary">
            <span>See your IT risk score — free</span>
            <ArrowRight size={18} />
          </Link>
          <Link to="/metrics" className="landing-button landing-button--ghost">
            View supporting metrics
          </Link>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
