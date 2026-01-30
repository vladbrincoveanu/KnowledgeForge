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

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth ?? 16}
        style={{ stroke: '#1168bd', strokeWidth: 2.8, cursor: 'pointer' }}
      />
      {label ? (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY + offset}px)`,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 6,
              padding: '2px 6px',
              fontSize: 11,
              fontWeight: 600,
              fontFamily: 'sans-serif',
              color: '#0f172a',
              pointerEvents: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};

export default C4Edge;
