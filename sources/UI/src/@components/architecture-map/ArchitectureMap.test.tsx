import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock ForceGraph2D (canvas) to avoid JSDOM canvas errors
vi.mock('react-force-graph-2d', () => ({
  default: () => <div data-testid="force-graph" />,
}));

// ArchitectureMap uses serviceExtractionAPI for GitHub extraction (not on mount)
vi.mock('@/services/api', () => ({
  serviceExtractionAPI: {
    extractFromGitHub: vi.fn(),
    getExtractionStatus: vi.fn(),
    getExtractionResults: vi.fn(),
  },
}));

import ArchitectureMap from './ArchitectureMap';

describe('ArchitectureMap', () => {
  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  test('renders without crashing', () => {
    render(<ArchitectureMap />);
    expect(screen.getByTestId('force-graph')).toBeInTheDocument();
  });

  test('shows empty state message when no services', () => {
    render(<ArchitectureMap />);
    expect(screen.getByText(/No services yet/i)).toBeInTheDocument();
  });

  test('renders legend items', () => {
    render(<ArchitectureMap />);
    expect(screen.getByText('Active-Dev')).toBeInTheDocument();
    expect(screen.getByText('Maintenance-Only')).toBeInTheDocument();
    expect(screen.getByText('Deprecated / Frozen')).toBeInTheDocument();
  });

  test('GitHub URL input is present', () => {
    render(<ArchitectureMap />);
    expect(screen.getByPlaceholderText(/https:\/\/github.com\/owner\/repo/i)).toBeInTheDocument();
  });

  test('Extract from GitHub button is initially disabled', () => {
    render(<ArchitectureMap />);
    const btn = screen.getByRole('button', { name: /Extract from GitHub/i });
    expect(btn).toBeDisabled();
  });

  test('Extract from GitHub button enables when URL is entered', () => {
    render(<ArchitectureMap />);
    const urlInput = screen.getByPlaceholderText(/https:\/\/github.com\/owner\/repo/i);
    const btn = screen.getByRole('button', { name: /Extract from GitHub/i });
    fireEvent.change(urlInput, { target: { value: 'https://github.com/foo/bar' } });
    expect(btn).not.toBeDisabled();
  });

  test('metadata textarea is present', () => {
    render(<ArchitectureMap />);
    expect(
      screen.getByPlaceholderText(/Paste YAML, JSON, or free-form service notes/i)
    ).toBeInTheDocument();
  });

  test('Extract metadata button is present', () => {
    render(<ArchitectureMap />);
    expect(screen.getByRole('button', { name: /Extract metadata/i })).toBeInTheDocument();
  });

  test('Add service manually button is present', () => {
    render(<ArchitectureMap />);
    expect(screen.getByRole('button', { name: /Add service manually/i })).toBeInTheDocument();
  });

  test('clicking Add service manually adds a service row', async () => {
    render(<ArchitectureMap />);
    const addBtn = screen.getByRole('button', { name: /Add service manually/i });
    fireEvent.click(addBtn);
    // After adding, new service input appears (no longer showing "No services yet")
    expect(screen.queryByText(/No services yet/i)).not.toBeInTheDocument();
  });

  test('clicking Extract metadata with empty textarea does nothing', () => {
    render(<ArchitectureMap />);
    const btn = screen.getByRole('button', { name: /Extract metadata/i });
    fireEvent.click(btn);
    // Empty state should persist
    expect(screen.getByText(/No services yet/i)).toBeInTheDocument();
  });

  // Smoke tests for repeated render stability
  for (let i = 1; i <= 5; i++) {
    test(`render smoke test ${i}`, () => {
      render(<ArchitectureMap />);
      expect(screen.getByTestId('force-graph')).toBeInTheDocument();
      cleanup();
    });
  }
});
