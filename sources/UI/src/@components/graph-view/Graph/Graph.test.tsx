import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Graph from './Graph';

// Mock react-force-graph-2d
vi.mock('react-force-graph-2d', () => ({
  default: React.forwardRef(function MockForceGraph(
    { onNodeClick, onLinkClick },
    ref
  ) {
    return (
      <div data-testid="force-graph-mock" ref={ref}>
        <div
          data-testid="test-node"
          onClick={() =>
            onNodeClick?.({ id: 'node1', label: 'Test Node', type: 'entity' })
          }
        >
          Test Node
        </div>
        <div
          data-testid="test-link"
          onClick={() =>
            onLinkClick?.({
              id: 'link1',
              source: 'node1',
              target: 'node2',
              label: 'Test Link',
            })
          }
        >
          Test Link
        </div>
      </div>
    );
  }),
}));

// Mock child components
vi.mock('../EdgeDetailsModal/EdgeDetailsModal', () => ({
  default: vi.fn(({ isOpen, edge, onClose }) =>
    isOpen ? (
      <div data-testid="edge-modal">
        <div>Edge Details: {edge?.label}</div>
        <button onClick={onClose}>Close</button>
      </div>
    ) : (
      <div style={{ display: 'none' }} />
    )
  ),
}));

vi.mock('../NodeDetailsModal/NodeDetailsModal', () => ({
  default: vi.fn(({ isOpen, node, onClose }) =>
    isOpen ? (
      <div data-testid="node-modal">
        <div>Node Details: {node?.label}</div>
        <button onClick={onClose}>Close</button>
      </div>
    ) : (
      <div style={{ display: 'none' }} />
    )
  ),
}));

const mockGraphData = {
  nodes: [
    {
      id: 'node1',
      label: 'Customer',
      type: 'entity',
      entityType: 'Person',
      confidence: 0.95,
    },
    {
      id: 'node2',
      label: 'Order',
      type: 'entity',
      entityType: 'Transaction',
      confidence: 0.88,
    },
  ],
  links: [
    {
      id: 'link1',
      source: 'node1',
      target: 'node2',
      label: 'places',
      confidence: 0.92,
    },
  ],
};

describe('Graph Component', () => {
  const mockOnEdgeClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the force graph component', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    expect(screen.getByTestId('force-graph-mock')).toBeInTheDocument();
  });

  it('displays node click functionality', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    const testNode = screen.getByTestId('test-node');
    fireEvent.click(testNode);

    expect(screen.getByTestId('node-modal')).toBeInTheDocument();
    expect(screen.getByText('Node Details: Test Node')).toBeInTheDocument();
  });

  it('displays edge click functionality', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    const testLink = screen.getByTestId('test-link');
    fireEvent.click(testLink);

    expect(screen.getByTestId('edge-modal')).toBeInTheDocument();
    expect(screen.getByText('Edge Details: Test Link')).toBeInTheDocument();
  });

  it('calls onEdgeClick prop when link is clicked', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    const testLink = screen.getByTestId('test-link');
    fireEvent.click(testLink);

    expect(mockOnEdgeClick).toHaveBeenCalledWith({
      id: 'link1',
      source: 'node1',
      target: 'node2',
      label: 'Test Link',
    });
  });

  it('closes node modal when close button is clicked', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    // Open node modal
    const testNode = screen.getByTestId('test-node');
    fireEvent.click(testNode);

    expect(screen.getByTestId('node-modal')).toBeInTheDocument();

    // Close modal
    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(screen.queryByTestId('node-modal')).not.toBeInTheDocument();
  });

  it('closes edge modal when close button is clicked', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    // Open edge modal
    const testLink = screen.getByTestId('test-link');
    fireEvent.click(testLink);

    expect(screen.getByTestId('edge-modal')).toBeInTheDocument();

    // Close modal
    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(screen.queryByTestId('edge-modal')).not.toBeInTheDocument();
  });

  it('clears edge selection when node is clicked', () => {
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    // First click a link to open edge modal
    const testLink = screen.getByTestId('test-link');
    fireEvent.click(testLink);
    expect(screen.getByTestId('edge-modal')).toBeInTheDocument();

    const testNode = screen.getByTestId('test-node');
    fireEvent.click(testNode);

    expect(screen.queryByTestId('edge-modal')).not.toBeInTheDocument();
    expect(screen.getByTestId('node-modal')).toBeInTheDocument();
  });

  it('handles empty graph data', () => {
    const emptyData = { nodes: [], links: [] };

    render(<Graph data={emptyData} onEdgeClick={mockOnEdgeClick} />);

    expect(screen.queryByTestId('force-graph-mock')).not.toBeInTheDocument();
    expect(screen.getByText('No Files Uploaded')).toBeInTheDocument();
  });

  it('works without onEdgeClick prop', () => {
    const mockOnEdgeClick = vi.fn();
    render(<Graph data={mockGraphData} onEdgeClick={mockOnEdgeClick} />);

    expect(() => {
      const testLink = screen.getByTestId('test-link');
      fireEvent.click(testLink);
    }).not.toThrow();

    expect(screen.getByTestId('edge-modal')).toBeInTheDocument();
  });
});
