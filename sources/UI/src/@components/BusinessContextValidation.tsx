import React, { useEffect, useMemo, useState } from 'react';
import {
  businessContextAPI,
  BusinessContextField,
  BusinessContextPayload,
  BusinessSnapshotDiffPayload,
} from '@/services/api';
import './BusinessContextValidation.scss';

/**
 * Represents the currently edited override form state.
 */
interface OverrideDraft {
  fieldPath: string;
  value: string;
  reason: string;
}

/**
 * Converts nullable values into concise human-readable labels.
 */
function renderValue(value: string | null): string {
  if (value == null || value.trim() === '') {
    return 'Not set';
  }
  return value;
}

/**
 * Renders confidence as an integer percentage label.
 */
function renderConfidence(confidence: number | null): string {
  if (confidence == null) {
    return 'N/A';
  }
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Maps field state into CSS class suffixes.
 */
function getStateClassName(field: BusinessContextField): string {
  return `state-${field.state}`;
}

/**
 * Business context review page for generated/override/effective validation.
 */
const BusinessContextValidation: React.FC = () => {
  const [payload, setPayload] = useState<BusinessContextPayload | null>(null);
  const [diff, setDiff] = useState<BusinessSnapshotDiffPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [savingFieldPath, setSavingFieldPath] = useState<string | null>(null);
  const [savingStatus, setSavingStatus] = useState<boolean>(false);
  const [expandedProvenance, setExpandedProvenance] = useState<Set<string>>(
    new Set()
  );
  const [draft, setDraft] = useState<OverrideDraft | null>(null);

  const systemId = 'wps';

  /**
   * Loads business context + snapshot diff for the active system.
   */
  const loadData = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const [contextPayload, diffPayload] = await Promise.all([
        businessContextAPI.getContext(systemId),
        businessContextAPI.getSnapshotDiff(systemId),
      ]);
      setPayload(contextPayload);
      setDiff(diffPayload);
    } catch (loadError) {
      const message =
        loadError instanceof Error
          ? loadError.message
          : 'Failed to load business context data.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const fields = useMemo(() => payload?.fields || [], [payload]);

  /**
   * Optimistically updates a field override and rolls back on API failure.
   */
  const handleOverrideSave = async (): Promise<void> => {
    if (!payload || !draft) {
      return;
    }
    if (draft.value.trim() === '' || draft.reason.trim() === '') {
      setError('Override value and reason are required.');
      return;
    }

    const previousFields = payload.fields;
    const optimisticFields = payload.fields.map(field =>
      field.field_path === draft.fieldPath
        ? {
            ...field,
            override_value: draft.value,
            effective_value: draft.value,
            state: 'overridden' as const,
            override_meta: {
              updated_by: 'ui-editor',
              field_updated_at: new Date().toISOString(),
              override_reason: draft.reason,
              status: 'active' as const,
              needs_review: false,
            },
          }
        : field
    );

    setPayload({ ...payload, fields: optimisticFields });
    setSavingFieldPath(draft.fieldPath);
    setError(null);

    try {
      const updatedField = await businessContextAPI.updateOverride(
        payload.system_id,
        draft.fieldPath,
        {
          value: draft.value,
          reason: draft.reason,
          updated_by: 'ui-editor',
        }
      );
      setPayload(current =>
        current
          ? {
              ...current,
              fields: current.fields.map(field =>
                field.field_path === updatedField.field_path
                  ? updatedField
                  : field
              ),
            }
          : current
      );
      setDraft(null);
    } catch (saveError) {
      setPayload({ ...payload, fields: previousFields });
      const message =
        saveError instanceof Error
          ? saveError.message
          : 'Failed to save override.';
      setError(message);
    } finally {
      setSavingFieldPath(null);
    }
  };

  /**
   * Optimistically updates review status and rolls back on failure.
   */
  const handleStatusChange = async (
    status: BusinessContextPayload['review_status']
  ): Promise<void> => {
    if (!payload || payload.review_status === status) {
      return;
    }
    const previousStatus = payload.review_status;
    setPayload({ ...payload, review_status: status });
    setSavingStatus(true);
    setError(null);

    try {
      await businessContextAPI.updateReviewStatus(payload.system_id, status);
    } catch (statusError) {
      setPayload({ ...payload, review_status: previousStatus });
      const message =
        statusError instanceof Error
          ? statusError.message
          : 'Failed to update review status.';
      setError(message);
    } finally {
      setSavingStatus(false);
    }
  };

  if (loading) {
    return (
      <div className="business-context-page">Loading context review...</div>
    );
  }

  if (!payload) {
    return (
      <div className="business-context-page">
        <div className="business-context-error">
          {error || 'Business context payload is unavailable.'}
        </div>
      </div>
    );
  }

  return (
    <div className="business-context-page">
      <div className="business-context-header">
        <div>
          <h2>{payload.system_label} Business Context</h2>
          <p>
            Snapshot {payload.snapshot.current_snapshot_id} extracted on{' '}
            {new Date(payload.snapshot.extracted_at).toLocaleString()}
          </p>
        </div>
        <button className="refresh-btn" onClick={() => void loadData()}>
          Refresh
        </button>
      </div>

      {error && <div className="business-context-error">{error}</div>}

      <section className="review-status-panel" aria-label="review-status-panel">
        <h3>Review Status</h3>
        <div className="status-buttons">
          {(['draft', 'reviewed', 'approved_for_publish'] as const).map(
            statusValue => (
              <button
                key={statusValue}
                className={
                  payload.review_status === statusValue
                    ? 'status-btn active'
                    : 'status-btn'
                }
                disabled={savingStatus}
                onClick={() => void handleStatusChange(statusValue)}
              >
                {statusValue}
              </button>
            )
          )}
        </div>
      </section>

      <section className="field-table" aria-label="field-state-table">
        <h3>Field Review</h3>
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Generated</th>
              <th>Override</th>
              <th>Effective</th>
              <th>State</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(field => (
              <React.Fragment key={field.field_path}>
                <tr>
                  <td>{field.label}</td>
                  <td>{renderValue(field.generated_value)}</td>
                  <td>{renderValue(field.override_value)}</td>
                  <td>{renderValue(field.effective_value)}</td>
                  <td>
                    <span className={`state-pill ${getStateClassName(field)}`}>
                      {field.state}
                    </span>
                  </td>
                  <td className="action-cell">
                    <button
                      onClick={() => {
                        setExpandedProvenance(prev => {
                          const next = new Set(prev);
                          if (next.has(field.field_path)) {
                            next.delete(field.field_path);
                          } else {
                            next.add(field.field_path);
                          }
                          return next;
                        });
                      }}
                      disabled={!field.provenance}
                    >
                      Provenance
                    </button>
                    <button
                      onClick={() =>
                        setDraft({
                          fieldPath: field.field_path,
                          value:
                            field.override_value ?? field.effective_value ?? '',
                          reason: '',
                        })
                      }
                    >
                      Edit Override
                    </button>
                  </td>
                </tr>

                {expandedProvenance.has(field.field_path) &&
                  field.provenance && (
                    <tr className="provenance-row">
                      <td colSpan={6}>
                        <div className="provenance-grid">
                          <div>
                            <strong>Source:</strong>{' '}
                            {field.provenance.source_type}
                          </div>
                          <div>
                            <strong>Path:</strong>{' '}
                            {field.provenance.source_path}
                          </div>
                          <div>
                            <strong>Rule:</strong>{' '}
                            {field.provenance.extraction_rule}
                          </div>
                          <div>
                            <strong>Confidence:</strong>{' '}
                            {renderConfidence(field.provenance.confidence)}
                          </div>
                          <div>
                            <strong>Last seen:</strong>{' '}
                            {new Date(
                              field.provenance.last_seen
                            ).toLocaleString()}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </section>

      {draft && (
        <section className="override-editor" aria-label="override-editor">
          <h3>Override: {draft.fieldPath}</h3>
          <label htmlFor="override-value">Value</label>
          <input
            id="override-value"
            value={draft.value}
            onChange={event =>
              setDraft(current =>
                current ? { ...current, value: event.target.value } : current
              )
            }
          />
          <label htmlFor="override-reason">Reason</label>
          <textarea
            id="override-reason"
            value={draft.reason}
            onChange={event =>
              setDraft(current =>
                current ? { ...current, reason: event.target.value } : current
              )
            }
          />
          <div className="override-actions">
            <button
              onClick={() => void handleOverrideSave()}
              disabled={savingFieldPath === draft.fieldPath}
            >
              {savingFieldPath === draft.fieldPath
                ? 'Saving...'
                : 'Save Override'}
            </button>
            <button className="secondary" onClick={() => setDraft(null)}>
              Cancel
            </button>
          </div>
        </section>
      )}

      <section className="snapshot-diff" aria-label="snapshot-diff">
        <h3>Snapshot Diff</h3>
        {!diff || diff.changes.length === 0 ? (
          <p>No extracted changes between snapshots.</p>
        ) : (
          <ul>
            {diff.changes.map(change => (
              <li key={change.field_path}>
                <div className="diff-heading">
                  <strong>{change.label}</strong>
                  {change.has_override_conflict && (
                    <span className="conflict-pill">Override conflict</span>
                  )}
                </div>
                <div className="diff-values">
                  <span>Previous: {renderValue(change.previous_value)}</span>
                  <span>Current: {renderValue(change.current_value)}</span>
                  {change.override_value && (
                    <span>Override: {renderValue(change.override_value)}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default BusinessContextValidation;
