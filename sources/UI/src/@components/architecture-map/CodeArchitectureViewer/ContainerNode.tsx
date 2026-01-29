import React from 'react';
import { Handle, Position } from 'reactflow';

interface ContainerNodeProps {
  data: {
    label: string;
    containerType?: string;
    technology?: string;
  };
}

const ContainerNode: React.FC<ContainerNodeProps> = ({ data }) => {
  return (
    <div className="container-node">
      <Handle type="target" position={Position.Left} />
      <div className="container-header">
        <div className="container-label">{data.label}</div>
        {data.containerType && (
          <div className="container-type">{data.containerType}</div>
        )}
        {data.technology && (
          <div className="container-tech">{data.technology}</div>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
};

export default ContainerNode;
