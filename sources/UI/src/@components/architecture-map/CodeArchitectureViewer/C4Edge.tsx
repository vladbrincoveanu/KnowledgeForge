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
  const fallbackLabel = label as string | undefined;

  // Show label box if we have protocol, description, or a plain label
  const hasContent = protocol || description || fallbackLabel;

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
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 6,
              padding: '3px 8px',
              fontSize: 11,
              fontFamily: 'sans-serif',
              color: '#0f172a',
              pointerEvents: 'none',
              textAlign: 'center',
              maxWidth: 160,
            }}
          >
            {protocol ? (
              <div style={{ fontWeight: 700 }}>[{protocol}]</div>
            ) : fallbackLabel ? (
              <div style={{ fontWeight: 600 }}>{fallbackLabel}</div>
            ) : null}
            {description && (
              <div
                style={{
                  fontStyle: 'italic',
                  color: '#64748b',
                  marginTop: (protocol || fallbackLabel) ? 2 : 0,
                  fontSize: 10,
                  lineHeight: '1.3',
                }}
              >
                {description}
              </div>
            )}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};

export default C4Edge;
