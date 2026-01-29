import React, { useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import {
  AlertTriangle,
  Plus,
  RefreshCw,
  Sparkles,
  Wand2,
  Github,
  Loader2,
} from 'lucide-react';
import './ArchitectureMap.scss';
import { GraphData } from '@/types';
import { serviceExtractionAPI } from '@/services/api';

type ServiceStatus = 'Active-Dev' | 'Maintenance-Only' | 'Deprecated / Frozen';

interface ServiceMetadata {
  id: string;
  name: string;
  domain: string;
  owner: string;
  status: ServiceStatus;
  description?: string;
  source?: string;
  risk?: string;
}

interface ChecklistItem {
  field: string;
  meaning: string;
  question: string;
  redFlag: string;
}

const statusPalette: Record<ServiceStatus | 'project', string> = {
  'Active-Dev': '#16a34a',
  'Maintenance-Only': '#f59e0b',
  'Deprecated / Frozen': '#ef4444',
  project: '#2563eb',
};

const checklist: ChecklistItem[] = [
  {
    field: 'domain',
    meaning:
      'Business area this service belongs to (e.g., Revenue Core, Checkout, User Profile)',
    question: 'Is this the right business bucket for my new feature?',
    redFlag: 'Feature work that does not match the tagged domain',
  },
  {
    field: 'owner',
    meaning: 'Squad or pod that owns and supports the service',
    question: 'Who do I need to book time with right now?',
    redFlag: 'No owner listed or routed to a generic mailbox',
  },
  {
    field: 'status',
    meaning:
      'Lifecycle stage: Active-Dev, Maintenance-Only, Deprecated / Frozen',
    question: 'Will engineers push back on work in this service?',
    redFlag: 'Status is Deprecated / Frozen or Maintenance-Only',
  },
];

const sampleRawInput = `checkout-api:
  domain: Revenue Core
  owner: Growth Squad
  status: active-dev
  notes: handles cart and payment sessions

user-profiles:
  domain: Identity
  owner: Profile Platform
  status: maintenance-only
  notes: merges identity from legacy stack

internal-telemetry:
  domain: Internal Tooling
  owner: Observability Guild
  status: deprecated
  notes: forwarding to new data mesh
`;

const defaultServices: ServiceMetadata[] = [
  {
    id: 'svc-checkout',
    name: 'Checkout API',
    domain: 'Revenue Core',
    owner: 'Growth Squad',
    status: 'Active-Dev',
    description: 'Cart orchestration and payment session handling.',
  },
  {
    id: 'svc-identity',
    name: 'User Profiles',
    domain: 'Identity',
    owner: 'Profile Platform',
    status: 'Maintenance-Only',
    description: 'Customer identity merge layer for legacy + new stack.',
    risk: 'Maintenance only',
  },
  {
    id: 'svc-telemetry',
    name: 'Internal Telemetry',
    domain: 'Internal Tooling',
    owner: 'Observability Guild',
    status: 'Deprecated / Frozen',
    description: 'Legacy metrics forwarder scheduled for shutdown.',
    risk: 'Status flagged',
  },
];

const normalizeStatus = (rawStatus?: string): ServiceStatus => {
  if (!rawStatus) return 'Active-Dev';
  const value = rawStatus.toLowerCase();
  if (/(deprecate|sunset|retire|frozen|legacy)/.test(value)) {
    return 'Deprecated / Frozen';
  }
  if (/(maint|stabil|support|bugfix)/.test(value)) {
    return 'Maintenance-Only';
  }
  return 'Active-Dev';
};

const statusConfidence = (status: ServiceStatus): number => {
  if (status === 'Active-Dev') return 0.95;
  if (status === 'Maintenance-Only') return 0.65;
  return 0.35;
};

const extractServicesFromText = (rawText: string): ServiceMetadata[] => {
  if (!rawText.trim()) return [];

  const blocks = rawText
    .split(/\n{2,}/)
    .map(block => block.trim())
    .filter(Boolean);

  return blocks.map((block, index) => {
    const nameMatch = block.match(/^[\w-.\s]+(?=:|$)/);
    const domainMatch = block.match(/domain\s*[:=]\s*([^\n]+)/i);
    const ownerMatch = block.match(
      /(owner|team|squad|pod|group)\s*[:=]\s*([^\n]+)/i
    );
    const statusMatch = block.match(/status\s*[:=]\s*([^\n]+)/i);

    const status = normalizeStatus(statusMatch?.[1]);
    const owner = ownerMatch?.[2]?.trim() || 'Unassigned';
    const domain = domainMatch?.[1]?.trim() || 'Unclassified';
    const name =
      nameMatch?.[0].trim().replace(/[:\s]+$/, '') ||
      `Service ${index + 1}`;

    const risk =
      !ownerMatch || status !== 'Active-Dev'
        ? !ownerMatch
          ? 'No owner listed'
          : 'Status flagged'
        : undefined;

    return {
      id: `svc-extracted-${index}`,
      name,
      domain,
      owner,
      status,
      description: block,
      source: 'Text extraction',
      risk,
    };
  });
};

const ArchitectureGraph: React.FC<{ data: GraphData }> = ({ data }) => {
  const canvasWidth =
    typeof window !== 'undefined'
      ? Math.max(320, Math.min(900, window.innerWidth - 220))
      : 900;
  const canvasHeight =
    typeof window !== 'undefined'
      ? Math.max(380, Math.min(560, window.innerHeight - 260))
      : 520;

  const nodeCanvasObject = (node: any, ctx: CanvasRenderingContext2D) => {
    const metadata = node.metadata || {};
    const status: ServiceStatus | 'project' =
      (metadata.status as ServiceStatus) || (node.type === 'project' ? 'project' : 'Active-Dev');
    const color = statusPalette[status] || '#2563eb';
    const radius = node.type === 'project' ? 14 : 10;

    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 1;
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();

    ctx.font = 'bold 12px "Inter", "Helvetica Neue", Arial, sans-serif';
    ctx.fillStyle = '#0f172a';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.label, node.x + radius + 8, node.y - 6);

    const subtitle = [metadata.domain, metadata.owner]
      .filter(Boolean)
      .join(' • ');
    if (subtitle) {
      ctx.font = '11px "Inter", "Helvetica Neue", Arial, sans-serif';
      ctx.fillStyle = '#475569';
      ctx.fillText(subtitle, node.x + radius + 8, node.y + 10);
    }
  };

  const nodePointerAreaPaint = (
    node: any,
    color: string,
    ctx: CanvasRenderingContext2D
  ) => {
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.arc(node.x, node.y, 18, 0, 2 * Math.PI, false);
    ctx.fill();
  };

  const linkColor = (link: any) => {
    const status = link.metadata?.status as ServiceStatus | undefined;
    if (status && statusPalette[status]) {
      return statusPalette[status];
    }
    return '#94a3b8';
  };

  return (
    <div className="architecture-graph">
      <ForceGraph2D
        graphData={data}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={nodePointerAreaPaint}
        linkColor={linkColor}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        linkWidth={link => Math.max(2, (link.confidence || 0.5) * 4)}
        width={canvasWidth}
        height={canvasHeight}
        backgroundColor="#ffffff"
      />
    </div>
  );
};

const ArchitectureMap: React.FC = () => {
  const [projectName, setProjectName] = useState('Architecture Blueprint');
  const [projectOwner, setProjectOwner] = useState('Architecture Guild');
  const [services, setServices] = useState<ServiceMetadata[]>([]);
  const [rawInput, setRawInput] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [hasExtractedData, setHasExtractedData] = useState(false);

  const graphData = useMemo<GraphData>(() => {
    const nodes = [
      {
        id: 'project-root',
        label: projectName || 'Project',
        type: 'project',
        metadata: {
          owner: projectOwner,
          status: 'Active-Dev',
          domain: 'Program',
        },
      },
      ...services.map(service => ({
        id: service.id,
        label: service.name,
        type: 'service',
        metadata: {
          owner: service.owner,
          domain: service.domain,
          status: service.status,
        },
      })),
    ];

    const links = services.map(service => ({
      id: `link-${service.id}`,
      source: 'project-root',
      target: service.id,
      label: service.domain,
      confidence: statusConfidence(service.status),
      metadata: {
        status: service.status,
      },
    }));

    return { nodes, links };
  }, [projectName, projectOwner, services]);

  const addService = () => {
    setServices(prev => [
      ...prev,
      {
        id: `svc-${Date.now()}`,
        name: `New Service ${prev.length + 1}`,
        domain: 'Unclassified',
        owner: 'Unassigned',
        status: 'Active-Dev',
        description: 'Describe the capability and lifecycle notes.',
      },
    ]);
    setHasExtractedData(true); // Show graph when service is added
  };

  const updateService = (
    id: string,
    patch: Partial<Omit<ServiceMetadata, 'id'>>
  ) => {
    setServices(prev =>
      prev.map(service =>
        service.id === id ? { ...service, ...patch } : service
      )
    );
  };

  const removeService = (id: string) => {
    setServices(prev => prev.filter(service => service.id !== id));
  };

  const handleExtract = () => {
    const extracted = extractServicesFromText(rawInput);
    if (extracted.length === 0) return;
    setServices(extracted);
    setHasExtractedData(true); // Show graph after extraction
  };

  const handleExtractFromGithub = async () => {
    if (!githubUrl.trim()) {
      setExtractionError('Please enter a GitHub URL');
      return;
    }

    setIsExtracting(true);
    setExtractionError(null);

    try {
      const response = await serviceExtractionAPI.extractFromGitHub(githubUrl, true);
      
      if (response.task_id) {
        // Poll for results
        let attempts = 0;
        const maxAttempts = 60; // 60 seconds max
        
        const pollInterval = setInterval(async () => {
          attempts++;
          
          try {
            const status = await serviceExtractionAPI.getExtractionStatus(response.task_id);
            
            if (status.status === 'completed') {
              clearInterval(pollInterval);
              setIsExtracting(false);
              
              const results = await serviceExtractionAPI.getExtractionResults(response.task_id);
              
              if (results.services && results.services.length > 0) {
                const extractedServices: ServiceMetadata[] = results.services.map((svc: any) => ({
                  id: svc.id || `svc-${Date.now()}-${Math.random()}`,
                  name: svc.name || svc.display_name || 'Unknown Service',
                  domain: svc.domain || svc.attributes?.domain || 'Unclassified',
                  owner: svc.owner || svc.attributes?.owner || 'Unassigned',
                  status: normalizeStatus(svc.status || svc.attributes?.status),
                  description: svc.description || svc.notes || svc.attributes?.description || '',
                  source: 'GitHub extraction',
                }));
                
                setServices(extractedServices);
                setGithubUrl(''); // Clear input on success
                setHasExtractedData(true); // Show graph after extraction
              } else {
                setExtractionError('No services found in the repository');
              }
            } else if (status.status === 'failed' || status.status === 'error') {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionError(status.message || 'Extraction failed');
            } else if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionError('Extraction timed out. Please check the task status manually.');
            }
          } catch (error: any) {
            if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              setIsExtracting(false);
              setExtractionError(error.message || 'Failed to get extraction status');
            }
          }
        }, 1000);
      } else {
        setIsExtracting(false);
        setExtractionError('Failed to start extraction');
      }
    } catch (error: any) {
      setIsExtracting(false);
      setExtractionError(error.message || 'Failed to extract from GitHub');
    }
  };

  const resetView = () => {
    setServices([]);
    setProjectName('Architecture Blueprint');
    setProjectOwner('Architecture Guild');
    setRawInput('');
    setHasExtractedData(false);
  };

  return (
    <div className="architecture-map">
      <div className="card" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div className="card-header">
          <Wand2 size={18} />
          <span>Extract Services</span>
        </div>
        <div className="project-form">
          <label>
            GitHub Repository URL
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <input
                type="text"
                value={githubUrl}
                onChange={e => setGithubUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                disabled={isExtracting}
                style={{ flex: 1 }}
              />
              <button
                className="primary"
                onClick={handleExtractFromGithub}
                disabled={isExtracting || !githubUrl.trim()}
                style={{ whiteSpace: 'nowrap' }}
              >
                {isExtracting ? (
                  <>
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Extracting...
                  </>
                ) : (
                  <>
                    <Github size={16} /> Extract from GitHub
                  </>
                )}
              </button>
            </div>
            {extractionError && (
              <div style={{ color: '#ef4444', fontSize: '14px', marginBottom: '8px' }}>
                <AlertTriangle size={14} /> {extractionError}
              </div>
            )}
          </label>
          <label>
            Or paste service manifests
            <textarea
              value={rawInput}
              onChange={e => setRawInput(e.target.value)}
              rows={8}
              placeholder="Paste YAML, JSON, or free-form service notes"
            />
          </label>
          <div className="project-actions">
            <button className="primary" onClick={handleExtract}>
              <Wand2 size={16} /> Extract metadata
            </button>
            <button className="ghost" onClick={addService} style={{ marginLeft: '8px' }}>
              <Plus size={16} /> Add service manually
            </button>
          </div>
        </div>
      </div>

      {hasExtractedData && (
      <div className="layout-grid">
        <div className="card service-list">
          <div className="card-header">
            <span>Services</span>
            <button className="ghost" onClick={addService}>
              <Plus size={14} /> Add service
            </button>
          </div>

          <div className="service-items">
            {services.map(service => (
              <div key={service.id} className="service-item">
                <div className="service-top">
                  <input
                    className="service-name"
                    value={service.name}
                    onChange={e =>
                      updateService(service.id, { name: e.target.value })
                    }
                  />
                  <select
                    value={service.status}
                  onChange={e =>
                      updateService(service.id, {
                        status: e.target.value as ServiceStatus,
                      })
                    }
                    className={`status ${service.status
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, '-')}`}
                  >
                    <option value="Active-Dev">Active-Dev</option>
                    <option value="Maintenance-Only">Maintenance-Only</option>
                    <option value="Deprecated / Frozen">Deprecated / Frozen</option>
                  </select>
                </div>

                <div className="service-fields">
                  <label>
                    Domain
                    <input
                      value={service.domain}
                      onChange={e =>
                        updateService(service.id, { domain: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Owner
                    <input
                      value={service.owner}
                      onChange={e =>
                        updateService(service.id, { owner: e.target.value })
                      }
                    />
                  </label>
                </div>

                <label className="service-notes">
                  Notes
                  <textarea
                    value={service.description || ''}
                    onChange={e =>
                      updateService(service.id, {
                        description: e.target.value,
                      })
                    }
                    rows={2}
                    placeholder="What does this service do? Any lifecycle caveats?"
                  />
                </label>

                <div className="service-footer">
                  <div className="tags">
                    <span className="pill subtle">{service.domain}</span>
                    <span className="pill subtle">{service.owner}</span>
                    {service.risk && (
                      <span className="pill warning">
                        <AlertTriangle size={12} /> {service.risk}
                      </span>
                    )}
                  </div>
                  <button className="ghost danger" onClick={() => removeService(service.id)}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card graph-card">
          <div className="card-header">
            <span>Architecture graph</span>
            <div className="legend">
              <span className="legend-item">
                <span className="dot" style={{ background: statusPalette['Active-Dev'] }} />
                Active-Dev
              </span>
              <span className="legend-item">
                <span className="dot" style={{ background: statusPalette['Maintenance-Only'] }} />
                Maintenance-Only
              </span>
              <span className="legend-item">
                <span className="dot" style={{ background: statusPalette['Deprecated / Frozen'] }} />
                Deprecated / Frozen
              </span>
            </div>
          </div>
          <ArchitectureGraph data={graphData} />
        </div>
      </div>
      )}
    </div>
  );
};

export default ArchitectureMap;
