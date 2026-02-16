import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

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
        <div
          className="node-stereotype"
          style={{
            fontSize: 10,
            opacity: 0.85,
            marginBottom: 2,
            textAlign: 'center',
          }}
        >
          {data.type === 'person' && (
            <span style={{ marginRight: 4 }}>👤</span>
          )}
          {stereotype}
        </div>
      ) : (
        <div className="node-header">{data.displayType}</div>
      )}

      <div className="node-content">
        <div className="node-name" title={data.label}>
          {formatLabel(data.label)}
        </div>
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
