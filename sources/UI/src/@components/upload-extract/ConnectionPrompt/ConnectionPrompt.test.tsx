import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConnectionPrompt from './ConnectionPrompt';

const mockConnection = {
  fileA: 'customers.csv',
  fileB: 'orders.csv',
  columnA: 'customer_id',
  columnB: 'customer_id',
  confidence: 0.85,
  llmAnalysis: {
    reasoning:
      'Both columns represent customer identifiers and likely establish a relationship between customer and order data.',
    business_context:
      'This connection allows linking customer information with their order history.',
    connection_type: 'FOREIGN KEY',
    suggested_join_strategy: 'inner join',
    potential_issues: [
      'Data type mismatch possible',
      'Null values in customer_id',
    ],
    recommendations: [
      'Validate data types before joining',
      'Handle null values appropriately',
    ],
    confidence_level: 'High' as const,
  },
};

describe('ConnectionPrompt Component', () => {
  const mockOnResponse = vi.fn();
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders connection prompt with basic information', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('AI-Detected Connection')).toBeInTheDocument();
    expect(screen.getByText('customers.csv')).toBeInTheDocument();
    expect(screen.getByText('orders.csv')).toBeInTheDocument();
    expect(screen.getAllByText('customer_id')).toHaveLength(2);
  });

  it('displays confidence percentage correctly', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('85% CONFIDENCE')).toBeInTheDocument();
  });

  it('shows AI analysis when available', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('AI Analysis')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Both columns represent customer identifiers and likely establish a relationship between customer and order data.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'This connection allows linking customer information with their order history.'
      )
    ).toBeInTheDocument();
  });

  it('displays potential issues when available', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('⚠️ Potential Issues')).toBeInTheDocument();
    expect(screen.getByText('Data type mismatch possible')).toBeInTheDocument();
    expect(screen.getByText('Null values in customer_id')).toBeInTheDocument();
  });

  it('displays recommendations when available', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('💡 Recommendations')).toBeInTheDocument();
    expect(
      screen.getByText('Validate data types before joining')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Handle null values appropriately')
    ).toBeInTheDocument();
  });

  it('calls onResponse with true when "Yes" button is clicked', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    const yesButton = screen.getByText('Yes, Create Connection');
    fireEvent.click(yesButton);

    expect(mockOnResponse).toHaveBeenCalledWith(true, mockConnection);
  });

  it('calls onResponse with false when "Cancel" button is clicked', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    expect(mockOnResponse).toHaveBeenCalledWith(false, mockConnection);
  });

  it('calls onClose when close button (X) is clicked', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    const closeButton = screen.getByRole('button', { name: '' }); // SVG close button
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('calls onClose when overlay is clicked', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    const overlay = document.querySelector('.connection-prompt-overlay');
    fireEvent.click(overlay!);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('does not close when clicking inside the modal content', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    const modalContent = document.querySelector('.connection-prompt');
    fireEvent.click(modalContent!);

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('handles escape key press to close modal', async () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('renders without LLM analysis', () => {
    const connectionWithoutAnalysis = {
      ...mockConnection,
      llmAnalysis: undefined,
    };

    render(
      <ConnectionPrompt
        connection={connectionWithoutAnalysis}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.queryByText('AI Analysis')).not.toBeInTheDocument();
    expect(screen.getByText('customers.csv')).toBeInTheDocument();
    expect(screen.getByText('orders.csv')).toBeInTheDocument();
  });

  it('works without onClose prop', () => {
    render(
      <ConnectionPrompt
        connection={mockConnection}
        onResponse={mockOnResponse}
      />
    );

    // Should render without errors
    expect(screen.getByText('AI-Detected Connection')).toBeInTheDocument();

    // Escape key should not cause errors
    expect(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    }).not.toThrow();
  });

  it('shows default connection type when not provided', () => {
    const connectionWithoutType = {
      ...mockConnection,
      llmAnalysis: {
        ...mockConnection.llmAnalysis!,
        connection_type: undefined,
      },
    };

    render(
      <ConnectionPrompt
        connection={connectionWithoutType}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('FOREIGN KEY')).toBeInTheDocument();
  });

  it('shows default join strategy when not provided', () => {
    const connectionWithoutStrategy = {
      ...mockConnection,
      llmAnalysis: {
        ...mockConnection.llmAnalysis!,
        suggested_join_strategy: undefined,
      },
    };

    render(
      <ConnectionPrompt
        connection={connectionWithoutStrategy}
        onResponse={mockOnResponse}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('inner join')).toBeInTheDocument();
  });
});
