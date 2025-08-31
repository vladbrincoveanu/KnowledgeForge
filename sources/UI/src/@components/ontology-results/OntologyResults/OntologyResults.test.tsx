import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OntologyResults from './OntologyResults';

// Mock the API
vi.mock('@/services/api', () => ({
  ontologyAPI: {
    getEntities: vi.fn(),
    getRelationships: vi.fn(),
    submitFeedback: vi.fn(),
    downloadResults: vi.fn(),
  },
  apiUtils: {
    handleApiError: vi.fn(),
    getConfidenceColor: vi.fn(confidence =>
      confidence > 0.9 ? 'green' : 'orange'
    ),
    formatConfidence: vi.fn(confidence => `${Math.round(confidence * 100)}%`),
  },
}));

const mockEntities = [
  {
    id: '1',
    name: 'Customer',
    entity_type: 'Person',
    confidence: 0.95,
    source_file: 'customers.csv',
    column_name: 'customer_name',
  },
  {
    id: '2',
    name: 'Product',
    entity_type: 'Item',
    confidence: 0.87,
    source_file: 'products.csv',
    column_name: 'product_name',
  },
];

const mockRelationships = [
  {
    id: '1',
    source_entity_id: '1',
    target_entity_id: '2',
    relationship_type: 'purchases',
    confidence: 0.92,
    source_file: 'orders.csv',
  },
];

const mockApiResponse = (items: typeof mockEntities = mockEntities) => ({
  items,
  total: items.length,
});

describe('OntologyResults Component', () => {
  const mockOnFeedbackSubmitted = vi.fn();

  beforeEach(async () => {
    vi.clearAllMocks();
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApiResponse(mockEntities)
    );
    (ontologyAPI.getRelationships as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApiResponse(mockRelationships)
    );
  });

  it('renders loading state initially', async () => {
    const { ontologyAPI } = await import('@/services/api');
    let resolveLoading;
    const loadingPromise = new Promise(resolve => {
      resolveLoading = resolve;
    });
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockReturnValue(loadingPromise);
    (ontologyAPI.getRelationships as ReturnType<typeof vi.fn>).mockReturnValue(loadingPromise);

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    // Check that the component renders (initially no entities loaded)
    expect(screen.getByText('Extraction Results')).toBeInTheDocument();
    expect(screen.getByText('Entities (0)')).toBeInTheDocument();
    
    resolveLoading!(mockApiResponse(mockEntities));
    await waitFor(() => {
      expect(screen.getByText('Entities (2)')).toBeInTheDocument();
    });
  });

  it('renders entities tab by default', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Customer')).toBeInTheDocument();
      expect(screen.getByText('Product')).toBeInTheDocument();
    });
  });

  it('switches to relationships tab when clicked', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Customer')).toBeInTheDocument();
    });

    const relationshipsTab = screen.getByText(/Relationships/);
    fireEvent.click(relationshipsTab);

    await waitFor(() => {
      expect(screen.getByText('purchases')).toBeInTheDocument();
    });
  });

  it('displays entity confidence as percentage', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('95%')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
    });
  });

  it('handles feedback submission for entities', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.submitFeedback as ReturnType<typeof vi.fn>).mockResolvedValue({ success: true });

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Customer')).toBeInTheDocument();
    });

    // Find and click the thumbs up button for the first entity
    const thumbsUpButtons = await screen.findAllByRole('button');
    const firstThumbsUp = thumbsUpButtons.find(btn =>
      btn.className.includes('positive')
    );
    fireEvent.click(firstThumbsUp!);

    // Now check for the feedback form
    const submitButton = await screen.findByText('Submit Feedback');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(ontologyAPI.submitFeedback).toHaveBeenCalledWith({
        type: 'positive',
        entity_id: '1',
        relationship_id: undefined,
        comment: '',
      });
    });
  });

  it('handles API errors gracefully', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('API Error'));

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/API Error/i)).toBeInTheDocument();
    });
  });

  it('displays pagination information', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/2 entities found/i)).toBeInTheDocument();
    });
  });

  it('handles download functionality', async () => {
    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Customer')).toBeInTheDocument();
    });

    const downloadButton = screen.getByText(/Export Results/i);
    fireEvent.click(downloadButton);

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  it('handles refresh functionality', async () => {
    const { ontologyAPI } = await import('@/services/api');

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Customer')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText(/Refresh/i);
    fireEvent.click(refreshButton);

    await waitFor(() => {
      // Called once on load for entities, once for relationships, then once for entities on refresh
      expect(ontologyAPI.getEntities).toHaveBeenCalledTimes(2);
    });
  });

  it('shows empty state when no data', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockResolvedValue(mockApiResponse([]));

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={mockOnFeedbackSubmitted}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/0 entities found/i)).toBeInTheDocument();
    });
  });
});
