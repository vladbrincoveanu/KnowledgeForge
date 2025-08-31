import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Settings from './Settings';

// Mock environment variables
vi.mock('import.meta', () => ({
  env: {
    VITE_API_URL: 'http://localhost:8000',
    VITE_API_KEY: 'test-api-key-12345',
  },
}));

describe('Settings Component', () => {
  const mockOnSettingsChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders settings form with default values', () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    expect(screen.getByLabelText(/API Base URL/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/API Key/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Default Confidence Threshold/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Auto-refresh Metrics/i)).toBeInTheDocument();
  });

  it('displays environment variable values in inputs', () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const apiUrlInput = screen.getByDisplayValue('http://localhost:8000');
    const apiKeyInput = screen.getByDisplayValue('test-api-key-12345');

    expect(apiUrlInput).toBeInTheDocument();
    expect(apiKeyInput).toBeInTheDocument();
  });

  it('updates input values when user types', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);

    fireEvent.change(apiUrlInput, { target: { value: 'http://new-api.com' } });

    await waitFor(() => {
      expect(apiUrlInput).toHaveValue('http://new-api.com');
    });
  });

  it('enables save button when settings are modified', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const saveButton = screen.getByRole('button', { name: /Save Settings/i });
    expect(saveButton).toBeDisabled();

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);
    fireEvent.change(apiUrlInput, {
      target: { value: 'http://modified-api.com' },
    });

    await waitFor(() => {
      expect(saveButton).toBeEnabled();
    });
  });

  it('calls onSettingsChange when save button is clicked', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);
    const saveButton = screen.getByRole('button', { name: /Save Settings/i });

    fireEvent.change(apiUrlInput, { target: { value: 'http://new-api.com' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockOnSettingsChange).toHaveBeenCalledWith({
        apiBaseUrl: 'http://new-api.com',
        apiKey: 'test-api-key-12345',
        confidenceThreshold: 0.7,
        autoRefreshMetrics: true,
      });
    });
  });

  it('updates confidence threshold when slider is moved', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const slider = screen.getByLabelText(/Default Confidence Threshold/i);

    fireEvent.change(slider, { target: { value: '0.9' } });

    await waitFor(() => {
      expect(slider).toHaveValue('0.9');
    });
  });

  it('toggles auto-refresh checkbox', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const checkbox = screen.getByLabelText(/Auto-refresh Metrics/i);
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(checkbox).not.toBeChecked();
    });
  });

  it('resets settings to defaults when reset button is clicked', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);
    const resetButton = screen.getByRole('button', {
      name: /Reset to Defaults/i,
    });

    // Modify a value first
    fireEvent.change(apiUrlInput, {
      target: { value: 'http://modified-api.com' },
    });

    // Reset to defaults
    fireEvent.click(resetButton);

    await waitFor(() => {
      expect(apiUrlInput).toHaveValue('http://localhost:8000');
    });
  });

  it('disables save button after saving', async () => {
    render(<Settings onSettingsChange={mockOnSettingsChange} />);

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);
    const saveButton = screen.getByRole('button', { name: /Save Settings/i });

    // Modify and save
    fireEvent.change(apiUrlInput, { target: { value: 'http://new-api.com' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(saveButton).toBeDisabled();
    });
  });

  it('handles missing onSettingsChange prop gracefully', async () => {
    render(<Settings />);

    const apiUrlInput = screen.getByLabelText(/API Base URL/i);
    const saveButton = screen.getByRole('button', { name: /Save Settings/i });

    fireEvent.change(apiUrlInput, { target: { value: 'http://new-api.com' } });

    // Should not throw an error
    expect(() => {
      fireEvent.click(saveButton);
    }).not.toThrow();
  });
});
