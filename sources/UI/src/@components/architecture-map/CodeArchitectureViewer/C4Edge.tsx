import {
  BaseEdge,
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
} from 'reactflow';

const getEdgeOffset = (id: string) => {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  const bucket = Math.abs(hash) % 5; // 0..4
  return (bucket - 2) * 10; // -20..20 px
};

const C4Edge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  label,
  data,
  interactionWidth,
}: EdgeProps) => {
  const offset = getEdgeOffset(id);
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY: sourceY + offset,
    targetX,
    targetY: targetY + offset,
    sourcePosition,
    targetPosition,
  });

  const protocol = data?.protocol as string | undefined;
  const description = data?.description as string | undefined;
  const businessLabel = data?.business_label as string | undefined;
  const fallbackLabel = label as string | undefined;
  const primaryLabel = businessLabel || description || fallbackLabel;

  // Show label box if we have protocol, description, or a plain label
  const hasContent = protocol || primaryLabel;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth ?? 16}
        style={{ stroke: '#1168bd', strokeWidth: 2.8, cursor: 'pointer' }}
      />
      {hasContent ? (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY + offset}px)`,
              background: '#f8fafc',
              border: '1px solid #cbd5e1',
              borderRadius: 10,
              padding: '4px 10px',
              fontSize: 11,
              fontFamily: 'Inter, sans-serif',
              color: '#0f172a',
              pointerEvents: 'none',
              textAlign: 'center',
              maxWidth: 220,
            }}
          >
            {primaryLabel && (
              <div
                style={{
                  fontWeight: 600,
                  color: '#0f172a',
                  lineHeight: 1.2,
                }}
              >
                {primaryLabel}
              </div>
            )}
            {protocol && (
              <div
                style={{
                  marginTop: primaryLabel ? 3 : 0,
                  display: 'inline-block',
                  padding: '1px 6px',
                  borderRadius: 999,
                  background: '#e2e8f0',
                  color: '#334155',
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                }}
              >
                {protocol}
              </div>
            )}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};

export default C4Edge;
