import React, { useMemo, useState } from 'react';

type ActorFeedback = {
  index: number;
  name?: string;
  description?: string;
  ignore?: boolean;
};

type ExternalDependencyFeedback = {
  index: number;
  name?: string;
  dependency_type?: 'BUSINESS_SYSTEM' | 'TECHNICAL_INFRA' | 'UNKNOWN';
  url?: string;
  protocol?: string;
  notes?: string;
  ignore?: boolean;
};

type RelationshipFeedback = {
  source: string;
  destination: string;
  description: string;
  relationship_type?: string;
  protocol?: string;
};

export type ContextFeedbackPayload = {
  system_name?: string;
  actors?: ActorFeedback[];
  external_dependencies?: ExternalDependencyFeedback[];
  relationships?: RelationshipFeedback[];
};

export default function ContextReviewDialog(props: {
  open: boolean;
  title?: string;
  submitting?: boolean;
  error?: string | null;
  initial: ContextFeedbackPayload;
  onCancel: () => void;
  onSubmit: (payload: ContextFeedbackPayload) => void;
}) {
  const { open, title, submitting, error, initial, onCancel, onSubmit } = props;
  const [systemName, setSystemName] = useState(initial.system_name || '');
  const [actors, setActors] = useState<ActorFeedback[]>(initial.actors || []);
  const [deps, setDeps] = useState<ExternalDependencyFeedback[]>(
    initial.external_dependencies || []
  );
  const [rels, setRels] = useState<RelationshipFeedback[]>(
    initial.relationships || []
  );

  const counts = useMemo(
    () => ({
      actors: actors.filter(a => !a.ignore).length,
      deps: deps.filter(d => !d.ignore).length,
      rels: rels.length,
    }),
    [actors, deps, rels]
  );

  if (!open) return null;

  return (
    <div className="context-review-modal-overlay" onClick={onCancel}>
      <div
        className="context-review-modal"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="context-review-modal__header">
          <div>
            <div className="context-review-modal__title">
              {title || 'Review System Context'}
            </div>
            <div className="context-review-modal__subtitle">
              Confirm actors, external systems, and relationship wording. This is
              used to fix accuracy in the final diagram.
            </div>
            {error ? (
              <div className="context-review-modal__error">{error}</div>
            ) : null}
          </div>
          <button className="context-review-modal__close" onClick={onCancel}>
            Close
          </button>
        </div>

        <div className="context-review-modal__body">
          <section className="context-review-section">
            <h3>System</h3>
            <div className="context-review-row">
              <label>System name</label>
              <input
                value={systemName}
                onChange={e => setSystemName(e.target.value)}
                placeholder="e.g. CMS / WPS"
              />
            </div>
          </section>

          <section className="context-review-section">
            <h3>Actors ({counts.actors})</h3>
            <div className="context-review-table">
              {actors.map((a, i) => (
                <div className="context-review-table__row" key={`actor-${a.index}-${i}`}>
                  <div className="context-review-table__cell">
                    <input
                      value={a.name || ''}
                      onChange={e => {
                        const next = [...actors];
                        next[i] = { ...a, name: e.target.value };
                        setActors(next);
                      }}
                      placeholder="Business name (e.g. Online Marketing User)"
                    />
                  </div>
                  <div className="context-review-table__cell">
                    <input
                      value={a.description || ''}
                      onChange={e => {
                        const next = [...actors];
                        next[i] = { ...a, description: e.target.value };
                        setActors(next);
                      }}
                      placeholder="What do they do in the CMS?"
                    />
                  </div>
                  <div className="context-review-table__cell context-review-table__cell--compact">
                    <label className="context-review-check">
                      <input
                        type="checkbox"
                        checked={!!a.ignore}
                        onChange={e => {
                          const next = [...actors];
                          next[i] = { ...a, ignore: e.target.checked };
                          setActors(next);
                        }}
                      />
                      Ignore
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="context-review-section">
            <h3>External Systems ({counts.deps})</h3>
            <div className="context-review-table context-review-table--deps">
              {deps.map((d, i) => (
                <div className="context-review-table__row" key={`dep-${d.index}-${i}`}>
                  <div className="context-review-table__cell">
                    <input
                      value={d.name || ''}
                      onChange={e => {
                        const next = [...deps];
                        next[i] = { ...d, name: e.target.value };
                        setDeps(next);
                      }}
                      placeholder="Business system/platform name"
                    />
                  </div>
                  <div className="context-review-table__cell context-review-table__cell--compact">
                    <select
                      value={d.dependency_type || 'BUSINESS_SYSTEM'}
                      onChange={e => {
                        const next = [...deps];
                        next[i] = {
                          ...d,
                          dependency_type: e.target
                            .value as ExternalDependencyFeedback['dependency_type'],
                        };
                        setDeps(next);
                      }}
                    >
                      <option value="BUSINESS_SYSTEM">Business system</option>
                      <option value="TECHNICAL_INFRA">Technical platform</option>
                      <option value="UNKNOWN">Unknown</option>
                    </select>
                  </div>
                  <div className="context-review-table__cell">
                    <input
                      value={d.protocol || ''}
                      onChange={e => {
                        const next = [...deps];
                        next[i] = { ...d, protocol: e.target.value };
                        setDeps(next);
                      }}
                      placeholder="Protocol (e.g. HTTPS, Kafka)"
                    />
                  </div>
                  <div className="context-review-table__cell">
                    <input
                      value={d.url || ''}
                      onChange={e => {
                        const next = [...deps];
                        next[i] = { ...d, url: e.target.value };
                        setDeps(next);
                      }}
                      placeholder="URL (optional)"
                    />
                  </div>
                  <div className="context-review-table__cell">
                    <input
                      value={d.notes || ''}
                      onChange={e => {
                        const next = [...deps];
                        next[i] = { ...d, notes: e.target.value };
                        setDeps(next);
                      }}
                      placeholder="Notes (optional)"
                    />
                  </div>
                  <div className="context-review-table__cell context-review-table__cell--compact">
                    <label className="context-review-check">
                      <input
                        type="checkbox"
                        checked={!!d.ignore}
                        onChange={e => {
                          const next = [...deps];
                          next[i] = { ...d, ignore: e.target.checked };
                          setDeps(next);
                        }}
                      />
                      Ignore
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="context-review-section">
            <h3>Relationships ({counts.rels})</h3>
            <div className="context-review-table context-review-table--rels">
              {rels.map((r, i) => (
                <div className="context-review-table__row" key={`rel-${i}`}>
                  <div className="context-review-table__cell context-review-table__cell--readonly">
                    {r.source} → {r.destination}
                  </div>
                  <div className="context-review-table__cell">
                    <input
                      value={r.description || ''}
                      onChange={e => {
                        const next = [...rels];
                        next[i] = { ...r, description: e.target.value };
                        setRels(next);
                      }}
                      placeholder="e.g. Publishes content updates"
                    />
                  </div>
                  <div className="context-review-table__cell context-review-table__cell--compact">
                    <input
                      value={r.protocol || ''}
                      onChange={e => {
                        const next = [...rels];
                        next[i] = { ...r, protocol: e.target.value };
                        setRels(next);
                      }}
                      placeholder="Protocol"
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="context-review-modal__actions">
          <button className="context-review-btn context-review-btn--ghost" onClick={onCancel}>
            Skip (use as-is)
          </button>
          <button
            className="context-review-btn context-review-btn--primary"
            disabled={!!submitting}
            onClick={() =>
              onSubmit({
                system_name: systemName.trim() || undefined,
                actors,
                external_dependencies: deps,
                relationships: rels,
              })
            }
          >
            {submitting ? 'Applying...' : 'Apply Corrections'}
          </button>
        </div>
      </div>
    </div>
  );
}
