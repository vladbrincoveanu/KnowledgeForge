import React from 'react';
// Use reactflow (v11) - not @xyflow/react
import { Handle, Position } from 'reactflow';

interface ContainerNodeProps {
  data: {
    label: string;
    containerType?: string;
    technology?: string;
    isGroup?: boolean;
    groupKind?: 'actors' | 'system' | 'business' | 'technical';
  };
}

const ContainerNode: React.FC<ContainerNodeProps> = ({ data }) => {
  const isGroup = Boolean(data.isGroup);

  return (
    <div
      className={`container-node ${isGroup ? 'container-group' : ''} ${
        isGroup && data.groupKind ? `group-${data.groupKind}` : ''
      }`}
    >
      {!isGroup && <Handle type="target" position={Position.Left} />}
      <div className="container-header">
        <div className="container-label">{data.label}</div>
        {data.containerType && (
          <div className="container-type">{data.containerType}</div>
        )}
        {data.technology && (
          <div className="container-tech">{data.technology}</div>
        )}
      </div>
      {!isGroup && <Handle type="source" position={Position.Right} />}
    </div>
  );
};

export default ContainerNode;
