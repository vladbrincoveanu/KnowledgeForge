import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import BusinessContextValidation from './BusinessContextValidation';

const mockGetContext = vi.fn();
const mockGetSnapshotDiff = vi.fn();
const mockUpdateOverride = vi.fn();
const mockUpdateReviewStatus = vi.fn();

vi.mock('@/services/api', () => ({
  businessContextAPI: {
    getContext: (...args: unknown[]) => mockGetContext(...args),
    getSnapshotDiff: (...args: unknown[]) => mockGetSnapshotDiff(...args),
    updateOverride: (...args: unknown[]) => mockUpdateOverride(...args),
    updateReviewStatus: (...args: unknown[]) => mockUpdateReviewStatus(...args),
  },
}));

const basePayload = {
  system_id: 'wps',
  system_label: 'WPS',
  review_status: 'draft' as const,
  snapshot: {
    current_snapshot_id: 'snap-a',
    previous_snapshot_id: 'snap-b',
    extracted_at: '2026-02-19T12:10:00Z',
  },
  fields: [
    {
      field_path: 'owner',
      label: 'Owner',
      generated_value: 'Platform Engineering',
      override_value: null,
      effective_value: 'Platform Engineering',
      state: 'generated' as const,
      confidence: 0.94,
      provenance: {
        source_type: 'codeowners',
        source_path: '/repos/wps/.github/CODEOWNERS',
        source_hash: 'sha',
        artifact_version: 'main',
        extraction_rule: 'owner_rule',
        confidence: 0.94,
        last_seen: '2026-02-19T12:00:00Z',
      },
      override_meta: null,
    },
    {
      field_path: 'domain',
      label: 'Domain',
      generated_value: 'Payments',
      override_value: 'Global Payments',
      effective_value: 'Global Payments',
      state: 'overridden' as const,
      confidence: 0.8,
      provenance: null,
      override_meta: {
        updated_by: 'sme',
        field_updated_at: '2026-02-19T12:00:00Z',
        override_reason: 'Business naming',
        status: 'active' as const,
        needs_review: false,
      },
    },
    {
      field_path: 'experts',
      label: 'Experts',
      generated_value: null,
      override_value: null,
      effective_value: null,
      state: 'missing' as const,
      confidence: null,
      provenance: null,
      override_meta: null,
    },
  ],
};

const baseDiff = {
  system_id: 'wps',
  current_snapshot_id: 'snap-a',
  previous_snapshot_id: 'snap-b',
  changes: [
    {
      field_path: 'domain',
      label: 'Domain',
      previous_value: 'Payments Core',
      current_value: 'Payments',
      has_override_conflict: true,
      override_value: 'Global Payments',
    },
  ],
};

describe('BusinessContextValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetContext.mockResolvedValue(basePayload);
    mockGetSnapshotDiff.mockResolvedValue(baseDiff);
    mockUpdateOverride.mockResolvedValue({
      ...basePayload.fields[0],
      override_value: 'Platform Ops',
      effective_value: 'Platform Ops',
      state: 'overridden',
    });
    mockUpdateReviewStatus.mockResolvedValue({ review_status: 'reviewed' });
  });

  test('renders field state badges for generated, overridden, and missing', async () => {
    render(<BusinessContextValidation />);
    expect(await screen.findByText('WPS Business Context')).toBeInTheDocument();
    expect(screen.getByText('generated')).toBeInTheDocument();
    expect(screen.getByText('overridden')).toBeInTheDocument();
    expect(screen.getByText('missing')).toBeInTheDocument();
  });

  test('shows provenance details including confidence when opened', async () => {
    render(<BusinessContextValidation />);
    await screen.findByText('WPS Business Context');
    fireEvent.click(screen.getAllByRole('button', { name: 'Provenance' })[0]);
    expect(screen.getByText(/Source:/)).toBeInTheDocument();
    expect(screen.getByText('94%')).toBeInTheDocument();
  });

  test('saves override with optimistic update and reason', async () => {
    let resolveRequest: (value: unknown) => void = () => {};
    const pendingRequest = new Promise(resolve => {
      resolveRequest = resolve;
    });
    mockUpdateOverride.mockReturnValueOnce(pendingRequest);

    render(<BusinessContextValidation />);
    await screen.findByText('WPS Business Context');

    fireEvent.click(
      screen.getAllByRole('button', { name: 'Edit Override' })[0]
    );
    fireEvent.change(screen.getByLabelText('Value'), {
      target: { value: 'Platform Ops' },
    });
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Org rename' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Override' }));

    expect(screen.getAllByText('Platform Ops').length).toBeGreaterThan(1);
    expect(mockUpdateOverride).toHaveBeenCalledWith(
      'wps',
      'owner',
      expect.objectContaining({
        value: 'Platform Ops',
        reason: 'Org rename',
      })
    );

    resolveRequest({
      ...basePayload.fields[0],
      override_value: 'Platform Ops',
      effective_value: 'Platform Ops',
      state: 'overridden',
      override_meta: {
        updated_by: 'ui-editor',
        field_updated_at: '2026-02-19T12:10:00Z',
        override_reason: 'Org rename',
        status: 'active',
        needs_review: false,
      },
    });

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Save Override' })
      ).not.toBeInTheDocument()
    );
  });

  test('rolls back override and shows error on save failure', async () => {
    mockUpdateOverride.mockRejectedValueOnce(new Error('Override save failed'));

    render(<BusinessContextValidation />);
    await screen.findByText('WPS Business Context');

    fireEvent.click(
      screen.getAllByRole('button', { name: 'Edit Override' })[0]
    );
    fireEvent.change(screen.getByLabelText('Value'), {
      target: { value: 'Platform Ops' },
    });
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Org rename' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Override' }));

    expect(await screen.findByText('Override save failed')).toBeInTheDocument();
    expect(screen.getAllByText('Platform Engineering').length).toBeGreaterThan(
      1
    );
  });

  test('updates review status controls and renders diff conflict indicator', async () => {
    render(<BusinessContextValidation />);
    await screen.findByText('WPS Business Context');

    fireEvent.click(screen.getByRole('button', { name: 'reviewed' }));
    await waitFor(() =>
      expect(mockUpdateReviewStatus).toHaveBeenCalledWith('wps', 'reviewed')
    );
    expect(screen.getByText('Override conflict')).toBeInTheDocument();
  });
});
