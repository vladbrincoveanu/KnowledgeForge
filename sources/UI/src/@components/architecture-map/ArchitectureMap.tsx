import React, { useMemo, useState, useRef, useEffect } from 'react';
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
  attributes?: {
    inferred_fields?: {
      [key: string]: {
        confidence?: string;
        source?: string;
      };
    };
    [key: string]: any;
  };
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
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });

  useEffect(() => {
    const updateDimensions = () => {
      if (graphContainerRef.current) {
        const rect = graphContainerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(320, rect.width - 32),
          height: Math.max(380, rect.height - 32),
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const canvasWidth = dimensions.width;
  const canvasHeight = dimensions.height;

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
    <div className="architecture-graph" ref={graphContainerRef}>
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
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const servicesListRef = useRef<HTMLDivElement>(null);

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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:337',message:'handleExtractFromGithub called',data:{githubUrl,hasExistingInterval:!!pollIntervalRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    if (!githubUrl.trim()) {
      setExtractionError('Please enter a GitHub URL');
      return;
    }

    // #region agent log
    if (pollIntervalRef.current) {
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:343',message:'Clearing existing interval before starting new extraction',data:{existingIntervalId:!!pollIntervalRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    // #endregion

    setIsExtracting(true);
    setExtractionError(null);

    try {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:347',message:'Calling extractFromGitHub API',data:{githubUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      const response = await serviceExtractionAPI.extractFromGitHub(githubUrl, true);
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:350',message:'extractFromGitHub response received',data:{taskId:response.task_id,status:response.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      if (response.task_id) {
        // Poll for results
        let attempts = 0;
        const maxAttempts = 120; // 120 seconds max (allow time for LLM enrichment)
        let lastProgress = -1;
        let stuckProgressAttempts = 0;
        const maxStuckAttempts = 30; // 30 seconds of no progress change = stuck
        
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:354',message:'Creating polling interval',data:{taskId:response.task_id,maxAttempts},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
        
        let lastLoggedStatus = '';
        let lastLoggedAttempt = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          
          try {
            const status = await serviceExtractionAPI.getExtractionStatus(response.task_id);
            
            // Detect stuck extraction (progress hasn't changed)
            const currentProgress = status.progress ?? 0;
            if (currentProgress === lastProgress && (status.status === 'extracting' || status.status === 'running')) {
              stuckProgressAttempts++;
            } else {
              stuckProgressAttempts = 0;
              lastProgress = currentProgress;
            }
            
            // Only log on state changes or every 30 seconds (30 attempts) to drastically reduce noise
            const shouldLog = status.status !== lastLoggedStatus || (attempts - lastLoggedAttempt) >= 30;
            if (shouldLog) {
              console.log(`[ArchitectureMap] Poll attempt ${attempts}: status="${status.status}", progress=${status.progress}, message="${status.message}"`);
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:360',message:'Status response received',data:{attempts,status:status.status,statusType:typeof status.status,progress:status.progress,message:status.message,stuckAttempts:stuckProgressAttempts},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
              lastLoggedStatus = status.status;
              lastLoggedAttempt = attempts;
            }
            
            // Detect if extraction is stuck (no progress for too long) - but only if still extracting
            // Don't show stuck error if it eventually completes
            if (stuckProgressAttempts >= maxStuckAttempts && (status.status === 'extracting' || status.status === 'running')) {
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:370',message:'Extraction appears stuck, clearing interval',data:{attempts,stuckAttempts:stuckProgressAttempts,progress:status.progress},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
              // #endregion
              
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setIsExtracting(false);
              setExtractionError(`Extraction appears to be stuck at ${Math.round((status.progress || 0) * 100)}% progress. The backend extraction may be hanging. Please check backend logs or try again.`);
              return;
            }
            
            // Handle all possible terminal states
            if (status.status === 'completed') {
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:361',message:'Status is completed, clearing interval',data:{attempts},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
              
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setIsExtracting(false);
              
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:431',message:'Fetching extraction results',data:{taskId:response.task_id},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
              
              let results;
              try {
                results = await serviceExtractionAPI.getExtractionResults(response.task_id);
              } catch (error: any) {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:435',message:'Error fetching results',data:{error:error?.message,response:error?.response?.data},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                // #endregion
                setExtractionError(`Failed to fetch extraction results: ${error?.message || 'Unknown error'}`);
                return;
              }
              
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:433',message:'Results received',data:{servicesCount:results.services?.length,servicesSample:results.services?.[0],hasServices:!!results.services},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
              
              if (results.services && results.services.length > 0) {
                const extractedServices: ServiceMetadata[] = results.services.map((svc: any, index: number) => {
                  // Handle different service formats from backend
                  // Ensure we handle null, undefined, and empty string values explicitly
                  const serviceId = String(svc.id || svc.service_id || `svc-extracted-${index}`);
                  const serviceName = String(svc.name || svc.display_name || svc.service_name || 'Unknown Service');
                  // Handle domain - can be null, so explicitly check
                  const serviceDomain = svc.domain != null && svc.domain !== '' 
                    ? String(svc.domain) 
                    : (svc.attributes?.domain != null && svc.attributes.domain !== '' 
                        ? String(svc.attributes.domain) 
                        : 'Unclassified');
                  // Handle owner - can be null
                  const serviceOwner = svc.owner != null && svc.owner !== ''
                    ? String(svc.owner)
                    : (svc.attributes?.owner != null && svc.attributes.owner !== ''
                        ? String(svc.attributes.owner)
                        : 'Unassigned');
                  // Handle status - can be string "unknown" or enum object
                  let serviceStatus = 'Active-Dev';
                  if (svc.status != null) {
                    if (typeof svc.status === 'string') {
                      serviceStatus = svc.status;
                    } else if (svc.status.value != null) {
                      serviceStatus = String(svc.status.value);
                    } else if (svc.attributes?.status != null) {
                      serviceStatus = String(svc.attributes.status);
                    }
                  }
                  // Handle description - can be null
                  const serviceDescription = svc.description != null && svc.description !== ''
                    ? String(svc.description)
                    : (svc.notes != null && svc.notes !== ''
                        ? String(svc.notes)
                        : (svc.attributes?.description != null && svc.attributes.description !== ''
                            ? String(svc.attributes.description)
                            : ''));
                  
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:453',message:'Mapping service',data:{index,serviceId,serviceName,serviceDomain,serviceOwner,serviceStatus,rawDomain:svc.domain,rawOwner:svc.owner,rawStatus:svc.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                  // #endregion
                  
                  return {
                    id: serviceId,
                    name: serviceName,
                    domain: serviceDomain,
                    owner: serviceOwner,
                    status: normalizeStatus(serviceStatus),
                    description: serviceDescription,
                    source: 'GitHub extraction',
                    attributes: svc.attributes || {},
                  };
                });
                
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:450',message:'Setting extracted services',data:{count:extractedServices.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
                
                setServices(extractedServices);
                setGithubUrl(''); // Clear input on success
                setHasExtractedData(true); // Show graph after extraction
              } else {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:451',message:'No services in results',data:{resultsKeys:Object.keys(results),services:results.services},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
                setExtractionError('No services found in the repository');
              }
            } else if (status.status === 'failed' || status.status === 'error') {
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:383',message:'Status is failed/error, clearing interval',data:{attempts,status:status.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
              // #endregion
              
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setIsExtracting(false);
              setExtractionError(status.message || 'Extraction failed');
            } else if (attempts >= maxAttempts) {
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:387',message:'Max attempts reached, clearing interval',data:{attempts,maxAttempts,lastStatus:status.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
              // #endregion
              
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setIsExtracting(false);
              setExtractionError('Extraction timed out. Please check the task status manually.');
            }
          } catch (error: any) {
            // #region agent log
            fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:392',message:'Error in poll attempt',data:{attempts,maxAttempts,errorMessage:error?.message,errorType:error?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
            // #endregion
            
            if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              pollIntervalRef.current = null;
              setIsExtracting(false);
              setExtractionError(error.message || 'Failed to get extraction status');
            }
          }
        }, 1000);
        
        pollIntervalRef.current = pollInterval;
      } else {
        setIsExtracting(false);
        setExtractionError('Failed to start extraction');
      }
    } catch (error: any) {
      setIsExtracting(false);
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:404',message:'Error in handleExtractFromGithub',data:{errorMessage:error?.message,errorResponse:error?.response?.data,status:error?.response?.status},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      const errorMsg = error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'Failed to extract from GitHub';
      setExtractionError(errorMsg);
    }
  };
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/ad3d13e5-e95a-477d-91b8-639047779d7a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ArchitectureMap.tsx:408',message:'Component unmounting, clearing interval',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  const resetView = () => {
    setServices([]);
    setProjectName('Architecture Blueprint');
    setProjectOwner('Architecture Guild');
    setRawInput('');
    setHasExtractedData(false);
  };

  return (
    <div className="architecture-map">
      <div className="architecture-layout">
        <div className="extract-section">
          <div className="card extract-card">
            <div className="card-header">
              <Wand2 size={18} />
              <span>Extract Services</span>
            </div>
            <div className="project-form">
              <label>
                GitHub Repository URL
                <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                  <input
                    type="text"
                    value={githubUrl}
                    onChange={e => setGithubUrl(e.target.value)}
                    onKeyDown={e => {
                      // Allow Ctrl+A / Cmd+A to select all
                      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                        e.stopPropagation();
                      }
                    }}
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
                  <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '8px' }}>
                    <AlertTriangle size={12} /> {extractionError}
                  </div>
                )}
              </label>
              <label>
                Or paste service manifests
                <textarea
                  value={rawInput}
                  onChange={e => setRawInput(e.target.value)}
                  onKeyDown={e => {
                    // Allow Ctrl+A / Cmd+A to select all
                    if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                      e.stopPropagation();
                    }
                  }}
                  rows={4}
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
        </div>

        <div className="main-grid">
          <div className="card service-list">
            <div className="card-header">
              <span>Services</span>
              <button className="ghost" onClick={addService}>
                <Plus size={14} /> Add service
              </button>
            </div>

            <div className="service-items" ref={servicesListRef}>
              {services.length === 0 ? (
                <div className="empty-services">
                  <p>No services yet. Extract from GitHub or add manually.</p>
                </div>
              ) : (
                services.map(service => (
                  <div key={service.id} className="service-item">
                    <div className="service-top">
                      <input
                        className="service-name"
                        value={service.name || ''}
                        onChange={e =>
                          updateService(service.id, { name: e.target.value })
                        }
                        onKeyDown={e => {
                          // Allow Ctrl+A / Cmd+A to select all
                          if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                            e.stopPropagation();
                          }
                        }}
                      />
                      <select
                        value={service.status || 'Active-Dev'}
                      onChange={e =>
                        updateService(service.id, {
                          status: e.target.value as ServiceStatus,
                        })
                      }
                        className={`status ${(service.status || 'Active-Dev')
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
                          value={service.domain || ''}
                          onChange={e =>
                            updateService(service.id, { domain: e.target.value })
                          }
                          onKeyDown={e => {
                            // Allow Ctrl+A / Cmd+A to select all
                            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                              e.stopPropagation();
                            }
                          }}
                        />
                      </label>
                      <label>
                        Owner
                        <input
                          value={service.owner || ''}
                          onChange={e =>
                            updateService(service.id, { owner: e.target.value })
                          }
                          onKeyDown={e => {
                            // Allow Ctrl+A / Cmd+A to select all
                            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                              e.stopPropagation();
                            }
                          }}
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
                        onKeyDown={e => {
                          // Allow Ctrl+A / Cmd+A to select all
                          if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                            e.stopPropagation();
                          }
                        }}
                        rows={2}
                        placeholder="What does this service do? Any lifecycle caveats?"
                      />
                    </label>

                    <div className="service-footer">
                      <div className="tags">
                        <span className="pill subtle">{service.domain || 'Unclassified'}</span>
                        <span className="pill subtle">{service.owner || 'Unassigned'}</span>
                        {service.risk && (
                          <span className="pill warning">
                            <AlertTriangle size={12} /> {service.risk}
                          </span>
                        )}
                        {service.attributes?.inferred_fields && Object.keys(service.attributes.inferred_fields).length > 0 && (
                          <>
                            {Object.entries(service.attributes.inferred_fields).map(([field, info]: [string, any]) => {
                              if (info?.confidence === 'low') {
                                return (
                                  <span key={field} className="pill inferred" title={`${field} inferred with low confidence (${info.source || 'unknown source'})`}>
                                    <Sparkles size={10} /> {field}
                                  </span>
                                );
                              }
                              return null;
                            })}
                          </>
                        )}
                      </div>
                      <button className="ghost danger" onClick={() => removeService(service.id)}>
                        Remove
                      </button>
                    </div>
                  </div>
                ))
              )}
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
      </div>
    </div>
  );
};

export default ArchitectureMap;
