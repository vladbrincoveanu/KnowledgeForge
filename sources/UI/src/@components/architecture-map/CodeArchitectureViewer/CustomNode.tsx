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

const CustomNode: React.FC<CustomNodeProps> = ({ data }) => {
  // Format the label to be more readable (replace underscores, limit length)
  const formatLabel = (label: string) => {
    const formatted = label.replace(/_/g, ' ');
    return formatted.length > 30
      ? formatted.substring(0, 27) + '...'
      : formatted;
  };

  const isContainer = data.type === 'container';

  return (
    <div className={`react-flow__node-custom node-type-${data.type}`}>
      <Handle
        type="target"
        position={isContainer ? Position.Left : Position.Top}
        className="custom-handle"
      />

      <div className="node-header">{data.displayType}</div>

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
