import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from '@testing-library/react';
import SystemMetrics from './SystemMetrics';

// Mock recharts
vi.mock('recharts', () => ({
  BarChart: vi.fn(({ children }) => (
    <div data-testid="bar-chart">{children}</div>
  )),
  Bar: vi.fn(() => <div data-testid="bar" />),
  Cell: vi.fn(() => <div data-testid="cell" />),
  PieChart: vi.fn(({ children }) => (
    <div data-testid="pie-chart">{children}</div>
  )),
  Pie: vi.fn(() => <div data-testid="pie" />),
  ResponsiveContainer: vi.fn(({ children }) => (
    <div data-testid="responsive-container">{children}</div>
  )),
  Tooltip: vi.fn(() => <div data-testid="tooltip" />),
  XAxis: vi.fn(() => <div data-testid="x-axis" />),
  YAxis: vi.fn(() => <div data-testid="y-axis" />),
  CartesianGrid: vi.fn(() => <div data-testid="cartesian-grid" />),
}));

// Mock the API
vi.mock('@/services/api', () => ({
  ontologyAPI: {
    getMetrics: vi.fn(),
    healthCheck: vi.fn(),
  },
  apiUtils: {
    formatTimestamp: vi.fn(timestamp => new Date(timestamp).toLocaleString()),
    handleApiError: vi.fn(),
  },
}));

const mockMetrics = {
  timestamp: '2024-01-01T12:00:00Z',
  system_metrics: {
    total_tasks: 150,
    completed_tasks: 145,
    failed_tasks: 5,
    success_rate: 0.97,
  },
  extraction_metrics: {
    total_entities_extracted: 1250,
    total_relationships_discovered: 856,
    average_processing_time: 2.3,
  },
  quality_metrics: {
    average_entity_confidence: 0.87,
    average_relationship_confidence: 0.85,
    data_coverage: 0.92,
  },
};

const mockHealth = {
  status: 'healthy' as const,
  timestamp: '2024-01-01T12:00:00Z',
  version: '1.0.0',
  dependencies: {
    database: true,
    llm_service: true,
    api: true,
  },
};

describe('SystemMetrics Component', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { ontologyAPI } = await import('@/services/api');
    ontologyAPI.getMetrics.mockResolvedValue(mockMetrics);
    ontologyAPI.healthCheck.mockResolvedValue(mockHealth);
  });

  it('renders loading state initially', () => {
    render(<SystemMetrics />);

    expect(screen.getByText(/Loading system metrics/i)).toBeInTheDocument();
  });

  it('displays system health status', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
      expect(screen.getByText('healthy')).toBeInTheDocument();
    });
  });

  it('displays key metrics', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument(); // total tasks
      expect(screen.getByText('145')).toBeInTheDocument(); // completed tasks
      expect(screen.getByText('5')).toBeInTheDocument(); // failed tasks
      expect(screen.getByText('97%')).toBeInTheDocument(); // success rate
    });
  });

  it('displays success rate correctly', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('97%')).toBeInTheDocument(); // 145/150 = 96.67% ~ 97%
    });
  });

  it('shows processing time', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('2.30 seconds')).toBeInTheDocument();
    });
  });

  it('displays charts for data visualization', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByTestId('bar-chart')).toBeInTheDocument(); // quality metrics
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument(); // task distribution
    });
  });

  it('handles refresh button click', async () => {
    const { ontologyAPI } = await import('@/services/api');

    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const refreshButton = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(ontologyAPI.getMetrics).toHaveBeenCalledTimes(2);
      expect(ontologyAPI.healthCheck).toHaveBeenCalledTimes(2);
    });
  });

  it('toggles auto-refresh when checkbox is clicked', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const autoRefreshToggle = screen.getByLabelText(/Auto-refresh/i);
    expect(autoRefreshToggle).toBeChecked();

    fireEvent.click(autoRefreshToggle);
    expect(autoRefreshToggle).not.toBeChecked();
  });

  it('handles API errors gracefully', async () => {
    const { ontologyAPI } = await import('@/services/api');
    ontologyAPI.getMetrics.mockRejectedValue(new Error('API Error'));
    ontologyAPI.healthCheck.mockRejectedValue(new Error('Health Check Error'));

    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText(/Error Loading Metrics/i)).toBeInTheDocument();
    });
  });

  it('displays different health statuses correctly', async () => {
    const { ontologyAPI } = await import('@/services/api');
    ontologyAPI.healthCheck.mockResolvedValue({
      ...mockHealth,
      status: 'degraded',
      dependencies: {
        ...mockHealth.dependencies,
        database: false,
      },
    });

    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('degraded')).toBeInTheDocument();
    });
  });

  it('shows version', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText('1.0.0')).toBeInTheDocument();
    });
  });

  it('displays timestamp information', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText(/Last updated:/i)).toBeInTheDocument();
    });
  });

  it('formats last check time', async () => {
    render(<SystemMetrics />);

    await waitFor(() => {
      expect(screen.getByText(/Last Check:/i)).toBeInTheDocument();
    });
  });

  it('handles empty metrics data', async () => {
    const { ontologyAPI } = await import('@/services/api');
    ontologyAPI.getMetrics.mockResolvedValue({
      timestamp: '2024-01-01T12:00:00Z',
      system_metrics: {
        total_tasks: 0,
        completed_tasks: 0,
        failed_tasks: 0,
        success_rate: 0,
      },
      extraction_metrics: {},
      quality_metrics: {},
    });

    render(<SystemMetrics />);

    await waitFor(() => {
      const totalTasks = screen
        .getByText('Total Tasks')
        .closest('.metric-card');
      expect(within(totalTasks).getByText('0')).toBeInTheDocument();
    });
  });
});
