import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OntologyResults from './OntologyResults';

// Mock recommendationAPI to prevent network calls and open timers
vi.mock('@/services/recommendationService', () => ({
  recommendationAPI: {
    getRecommendations: vi.fn(),
    generateRecommendations: vi.fn(),
    generateEdgeRecommendations: vi.fn(),
    submitRecommendationFeedback: vi.fn(),
  },
}));

// Mock the ontology API
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

const mockApiResponse = (items: typeof mockEntities | typeof mockRelationships) => ({
  items,
  total: items.length,
});

describe('OntologyResults Component', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { ontologyAPI } = await import('@/services/api');
    const { recommendationAPI } = await import('@/services/recommendationService');
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApiResponse(mockEntities)
    );
    (ontologyAPI.getRelationships as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApiResponse(mockRelationships)
    );
    // Return a non-404 error so no retry timer is set
    (recommendationAPI.getRecommendations as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('No recommendations')
    );
  });

  it('renders loading state initially', async () => {
    const { ontologyAPI } = await import('@/services/api');
    let resolveLoading: (value: unknown) => void;
    const loadingPromise = new Promise(resolve => {
      resolveLoading = resolve;
    });
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockReturnValue(loadingPromise);
    (ontologyAPI.getRelationships as ReturnType<typeof vi.fn>).mockReturnValue(loadingPromise);

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    expect(screen.getByText('Extraction Results')).toBeInTheDocument();
    expect(screen.getByText('Entities (0)')).toBeInTheDocument();

    resolveLoading!(mockApiResponse(mockEntities));
    await waitFor(() => {
      expect(screen.getByText('Entities (2)')).toBeInTheDocument();
    });
  });

  it('updates tab labels with loaded data counts', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Entities (2)')).toBeInTheDocument();
      expect(screen.getByText('Relationships (1)')).toBeInTheDocument();
    });
  });

  it('shows relationship data when relationships tab is clicked', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Relationships (1)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Relationships (1)'));

    await waitFor(() => {
      expect(screen.getByText('Discovered Relationships')).toBeInTheDocument();
      expect(screen.getByText('purchases')).toBeInTheDocument();
    });
  });

  it('displays relationship confidence as percentage', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Relationships (1)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Relationships (1)'));

    await waitFor(() => {
      expect(screen.getByText('92%')).toBeInTheDocument();
    });
  });

  it('handles feedback submission for relationships', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.submitFeedback as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: true,
    });
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    // Switch to relationships tab
    await waitFor(() => {
      expect(screen.getByText('Relationships (1)')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Relationships (1)'));

    // Wait for the relationship to appear
    await waitFor(() => {
      expect(screen.getByText('purchases')).toBeInTheDocument();
    });

    // Click the thumbs up button for the relationship
    const thumbsUpButtons = screen.getAllByRole('button');
    const feedbackBtn = thumbsUpButtons.find(btn =>
      btn.className.includes('positive')
    );
    fireEvent.click(feedbackBtn!);

    // Feedback form should appear
    const submitButton = await screen.findByText('Submit Feedback');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(ontologyAPI.submitFeedback).toHaveBeenCalledWith({
        type: 'positive',
        entity_id: undefined,
        relationship_id: '1',
        comment: '',
      });
    });

    alertSpy.mockRestore();
  });

  it('handles API errors gracefully', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.getEntities as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('API Error')
    );

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/API Error/i)).toBeInTheDocument();
    });
  });

  it('shows relationships count in relationships tab', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Relationships (1)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Relationships (1)'));

    await waitFor(() => {
      expect(screen.getByText('1 relationships found')).toBeInTheDocument();
    });
  });

  it('shows Export Results button', async () => {
    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    expect(screen.getByText('Export Results')).toBeInTheDocument();
  });

  it('handles download functionality', async () => {
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Entities (2)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Export Results/i));

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  it('handles refresh functionality', async () => {
    const { ontologyAPI } = await import('@/services/api');

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Entities (2)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Refresh'));

    await waitFor(() => {
      // Called once on initial load, once more on refresh
      expect(ontologyAPI.getEntities).toHaveBeenCalledTimes(2);
    });
  });

  it('shows empty relationship count when no relationships', async () => {
    const { ontologyAPI } = await import('@/services/api');
    (ontologyAPI.getRelationships as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockApiResponse([])
    );

    render(
      <OntologyResults
        taskId="test-task-123"
        onFeedbackSubmitted={vi.fn()}
        showNotification={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Relationships (0)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Relationships (0)'));

    await waitFor(() => {
      expect(screen.getByText('0 relationships found')).toBeInTheDocument();
    });
  });
});
