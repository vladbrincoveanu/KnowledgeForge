import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import {
  Boxes,
  Building2,
  Cloud,
  CreditCard,
  Database,
  GitBranch,
  Mail,
  MessageSquare,
  Server,
  ShieldAlert,
  User,
} from 'lucide-react';

interface CustomNodeProps {
  data: {
    label: string;
    type: string;
    displayType: string;
    fullName?: string;
    file?: string;
    line?: number;
    isExternal?: boolean;
    decorators?: string[];
    attributes?: Record<string, any>;
  };
}

const EXTERNAL_TYPES = new Set([
  'external_system',
  'external_service',
  'messaging',
  'cache',
  'database',
  'logging',
]);

interface C4Style {
  bg: string;
  color: string;
  stereotype: string | null;
  isC4: boolean;
}

const getC4Style = (type: string): C4Style => {
  if (type === 'system') {
    return { bg: '#1168bd', color: 'white', stereotype: '«system»', isC4: true };
  }
  if (type === 'person') {
    return { bg: '#08427b', color: 'white', stereotype: '«person»', isC4: true };
  }
  if (EXTERNAL_TYPES.has(type)) {
    return { bg: '#999999', color: 'white', stereotype: '«external system»', isC4: true };
  }
  return { bg: '', color: '', stereotype: null, isC4: false };
};

const toKeywordText = (value?: string) =>
  String(value || '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .trim();

type BrandKey =
  | 'google-analytics'
  | 'mixpanel'
  | 'sentry'
  | 'stripe'
  | 'slack'
  | 'github'
  | 'google-cloud'
  | 'resend'
  | 'bitbucket'
  | 'mongodb'
  | 'redis'
  | 'kafka'
  | 'rabbitmq'
  | 'sql-server'
  | null;

const detectBrand = (value?: string): BrandKey => {
  const v = toKeywordText(value);
  if (!v) return null;
  if (/google analytics|ga4|analytics/.test(v)) return 'google-analytics';
  if (/mixpanel/.test(v)) return 'mixpanel';
  if (/sentry/.test(v)) return 'sentry';
  if (/stripe/.test(v)) return 'stripe';
  if (/slack/.test(v)) return 'slack';
  if (/github|npm registry|npm/.test(v)) return 'github';
  if (/google cloud|gcp/.test(v)) return 'google-cloud';
  if (/resend|sendgrid|mailgun/.test(v)) return 'resend';
  if (/bitbucket/.test(v)) return 'bitbucket';
  if (/mongodb|mongo/.test(v)) return 'mongodb';
  if (/redis/.test(v)) return 'redis';
  if (/kafka/.test(v)) return 'kafka';
  if (/rabbitmq/.test(v)) return 'rabbitmq';
  if (/sql server|postgres|mysql|mssql/.test(v)) return 'sql-server';
  return null;
};

const BrandGlyph: React.FC<{ brand: BrandKey }> = ({ brand }) => {
  switch (brand) {
    case 'google-analytics':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="4" y="11" width="4" height="9" rx="2" fill="#f59e0b" />
          <rect x="10" y="7" width="4" height="13" rx="2" fill="#fbbf24" />
          <circle cx="18" cy="6" r="3" fill="#f97316" />
        </svg>
      );
    case 'mixpanel':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="8" cy="12" r="5" fill="#6b7280" />
          <circle cx="14" cy="10" r="5" fill="#9ca3af" />
          <circle cx="18" cy="14" r="5" fill="#111827" />
        </svg>
      );
    case 'sentry':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path
            d="M4 14c1.2-5 5-8 10-8 2.8 0 5.1 1 6 3"
            fill="none"
            stroke="#111827"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M20 10c-.3 5-3.8 8-8.5 8-3 0-5.2-1.2-6.5-3.5"
            fill="none"
            stroke="#374151"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      );
    case 'stripe':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="3" y="4" width="18" height="4" rx="2" fill="#635bff" />
          <rect x="3" y="10" width="13" height="4" rx="2" fill="#635bff" />
          <rect x="3" y="16" width="10" height="4" rx="2" fill="#635bff" />
        </svg>
      );
    case 'slack':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="4" y="10" width="6" height="3" rx="1.5" fill="#e11d48" />
          <rect x="7" y="4" width="3" height="6" rx="1.5" fill="#f59e0b" />
          <rect x="11" y="14" width="6" height="3" rx="1.5" fill="#3b82f6" />
          <rect x="14" y="8" width="3" height="6" rx="1.5" fill="#16a34a" />
        </svg>
      );
    case 'github':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="9" fill="#111827" />
          <text
            x="12"
            y="15"
            textAnchor="middle"
            fontSize="8"
            fontWeight="700"
            fill="#fff"
          >
            GH
          </text>
        </svg>
      );
    case 'google-cloud':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path
            d="M8 17a4 4 0 1 1 1.3-7.8A4.5 4.5 0 0 1 18 11h.5a3 3 0 1 1 0 6H8z"
            fill="#3b82f6"
          />
        </svg>
      );
    case 'resend':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="3" y="3" width="18" height="18" rx="4" fill="#374151" />
          <text
            x="12"
            y="15"
            textAnchor="middle"
            fontSize="9"
            fontWeight="700"
            fill="#fff"
          >
            R
          </text>
        </svg>
      );
    case 'bitbucket':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M4 4h16l-2 14H7L4 4z" fill="#2563eb" />
          <path d="M9 10h6l-1 5h-4l-1-5z" fill="#93c5fd" />
        </svg>
      );
    case 'mongodb':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M12 3c2.5 3.2 4 6.2 4 9.2 0 3.4-1.8 6.4-4 8.8-2.2-2.4-4-5.4-4-8.8 0-3 1.5-6 4-9.2z" fill="#16a34a" />
        </svg>
      );
    case 'redis':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="4" y="5" width="16" height="4" rx="1.5" fill="#dc2626" />
          <rect x="5" y="10" width="14" height="4" rx="1.5" fill="#ef4444" />
          <rect x="6" y="15" width="12" height="4" rx="1.5" fill="#f87171" />
        </svg>
      );
    case 'kafka':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="5" r="2" fill="#374151" />
          <circle cx="7" cy="12" r="2" fill="#374151" />
          <circle cx="17" cy="12" r="2" fill="#374151" />
          <circle cx="12" cy="19" r="2" fill="#374151" />
          <path d="M12 7v10M9 12h6" stroke="#6b7280" strokeWidth="1.5" />
        </svg>
      );
    case 'rabbitmq':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="7" y="8" width="10" height="9" rx="3" fill="#f97316" />
          <rect x="8" y="4" width="3" height="6" rx="1.5" fill="#fb923c" />
          <rect x="13" y="4" width="3" height="6" rx="1.5" fill="#fb923c" />
        </svg>
      );
    case 'sql-server':
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <ellipse cx="12" cy="6" rx="6" ry="2.6" fill="#64748b" />
          <path d="M6 6v9c0 1.4 2.7 2.6 6 2.6s6-1.2 6-2.6V6" fill="#94a3b8" />
          <ellipse cx="12" cy="15" rx="6" ry="2.6" fill="#64748b" />
        </svg>
      );
    default:
      return null;
  }
};

const getNodeIcon = (data: CustomNodeProps['data']) => {
  const label = toKeywordText(data.fullName || data.label);
  const depType = String(data.attributes?.dependency_type || '').toUpperCase();

  if (data.type === 'person') return User;
  if (data.type === 'system') return Boxes;
  if (data.type === 'container' || data.type === 'component') return Server;

  if (depType === 'TECHNICAL_INFRA') return Server;
  if (/(postgres|mysql|sql|mongo|redis|db|database|storage|s3)/.test(label))
    return Database;
  if (/(stripe|paypal|payment|billing|invoice)/.test(label)) return CreditCard;
  if (/(mail|email|smtp|resend|sendgrid)/.test(label)) return Mail;
  if (/(slack|chat|messag|notification)/.test(label)) return MessageSquare;
  if (/(github|gitlab|bitbucket|npm|registry|repo)/.test(label))
    return GitBranch;
  if (/(cloud|aws|gcp|azure|kubernetes|cluster)/.test(label)) return Cloud;
  if (/(sentry|monitor|alert|incident|observability)/.test(label))
    return ShieldAlert;

  return Building2;
};

const CustomNode: React.FC<CustomNodeProps> = ({ data }) => {
  // Format the label to be more readable (replace underscores, limit length)
  const formatLabel = (label: string) => {
    const formatted = label.replace(/_/g, ' ');
    return formatted.length > 30
      ? formatted.substring(0, 27) + '...'
      : formatted;
  };

  const isContainer = data.type === 'container';
  const { bg, color, stereotype, isC4 } = getC4Style(data.type);
  const Icon = getNodeIcon(data);
  const brand = detectBrand(`${data.fullName || ''} ${data.label || ''}`);
  const iconVisual = brand ? <BrandGlyph brand={brand} /> : <Icon size={16} />;

  return (
    <div
      className={`react-flow__node-custom node-type-${data.type}`}
      style={isC4 ? { background: bg, color, borderColor: bg } : undefined}
    >
      <Handle
        type="target"
        position={isContainer ? Position.Left : Position.Top}
        className="custom-handle"
      />

      {stereotype ? (
        <div className="node-stereotype">
          <span className="node-icon">
            {iconVisual}
          </span>
          <span>{stereotype}</span>
        </div>
      ) : (
        <div className="node-header">{data.displayType}</div>
      )}

      <div className="node-content">
        <div className="node-name" title={data.label}>
          {formatLabel(data.label)}
        </div>
        {!stereotype && (
          <div className="node-subline">
            <span className="node-icon">
              {iconVisual}
            </span>
            <span>{data.displayType}</span>
          </div>
        )}
        {data.isExternal && (
          <div className="node-badge external-badge">External</div>
        )}
        {data.file && <div className="node-file">{data.file}</div>}
      </div>

      <Handle
        type="source"
        position={isContainer ? Position.Right : Position.Bottom}
        className="custom-handle"
      />
    </div>
  );
};

export default memo(CustomNode);
