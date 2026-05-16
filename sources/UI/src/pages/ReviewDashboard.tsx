import React, { useState, useEffect } from "react";
import { reviewService, ReviewItem } from "../services/reviewService";

export const ReviewDashboard: React.FC = () => {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [runId, setRunId] = useState("latest");
  const [loading, setLoading] = useState(false);
  const [overrideField, setOverrideField] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState("");

  const loadPending = async () => {
    setLoading(true);
    try {
      const data = await reviewService.listPending(runId);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load review items:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPending();
  }, [runId]);

  const handleApprove = async (id: string) => {
    try {
      await reviewService.approve(id);
      await loadPending();
    } catch (err) {
      console.error("Failed to approve item:", err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await reviewService.reject(id);
      await loadPending();
    } catch (err) {
      console.error("Failed to reject item:", err);
    }
  };

  const handleOverride = async (id: string) => {
    try {
      await reviewService.override(id, overrideValue);
      setOverrideField(null);
      setOverrideValue("");
      await loadPending();
    } catch (err) {
      console.error("Failed to override item:", err);
    }
  };

  const handleBulkApprove = async () => {
    try {
      await reviewService.bulkApprove(runId);
      await loadPending();
    } catch (err) {
      console.error("Failed to bulk approve:", err);
    }
  };

  return (
    <div style={{ padding: "2rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "1.5rem",
        }}
      >
        <h1>Review Queue</h1>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            placeholder="Extraction run ID"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            style={{
              padding: "0.5rem",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
          />
          <button onClick={loadPending} style={{ padding: "0.5rem 1rem" }}>
            Load
          </button>
          <button
            onClick={handleBulkApprove}
            style={{
              padding: "0.5rem 1rem",
              background: "#16a34a",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
            }}
          >
            Bulk Approve ≥0.85
          </button>
        </div>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : total === 0 ? (
        <p>No pending items. All clear!</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr
              style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}
            >
              <th style={{ padding: "0.5rem" }}>Field</th>
              <th style={{ padding: "0.5rem" }}>Confidence</th>
              <th style={{ padding: "0.5rem" }}>Candidates</th>
              <th style={{ padding: "0.5rem" }}>LLM Suggestion</th>
              <th style={{ padding: "0.5rem" }}>Evidence</th>
              <th style={{ padding: "0.5rem" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "0.75rem" }}>{item.field}</td>
                <td style={{ padding: "0.75rem" }}>
                  <span
                    style={{
                      background:
                        item.confidence < 0.5
                          ? "#fee2e2"
                          : item.confidence < 0.7
                            ? "#fef3c7"
                            : "#d1fae5",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "9999px",
                      fontSize: "0.875rem",
                    }}
                  >
                    {item.confidence.toFixed(2)}
                  </span>
                </td>
                <td style={{ padding: "0.75rem" }}>
                  {item.candidate_values.map((v, i) => (
                    <div key={i} style={{ marginBottom: "0.25rem" }}>
                      {v}
                    </div>
                  ))}
                </td>
                <td
                  style={{
                    padding: "0.75rem",
                    fontStyle: "italic",
                    color: "#374151",
                  }}
                >
                  {item.llm_suggestion ?? "—"}
                </td>
                <td
                  style={{
                    padding: "0.75rem",
                    fontSize: "0.75rem",
                    color: "#6b7280",
                    maxWidth: "200px",
                  }}
                >
                  {item.evidence.slice(0, 2).map((e, i) => (
                    <div key={i}>
                      <code>{e.source}</code>: {e.snippet?.slice(0, 60)}
                    </div>
                  ))}
                </td>
                <td style={{ padding: "0.75rem" }}>
                  <div style={{ display: "flex", gap: "0.25rem" }}>
                    <button
                      onClick={() => handleApprove(item.id)}
                      style={{
                        padding: "0.25rem 0.5rem",
                        background: "#16a34a",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(item.id)}
                      style={{
                        padding: "0.25rem 0.5rem",
                        background: "#dc2626",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => setOverrideField(item.id)}
                      style={{
                        padding: "0.25rem 0.5rem",
                        background: "#6b7280",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      Override
                    </button>
                  </div>
                  {overrideField === item.id && (
                    <div
                      style={{
                        marginTop: "0.5rem",
                        display: "flex",
                        gap: "0.25rem",
                      }}
                    >
                      <input
                        value={overrideValue}
                        onChange={(e) => setOverrideValue(e.target.value)}
                        placeholder="Correct value"
                        style={{
                          padding: "0.25rem",
                          border: "1px solid #ccc",
                          borderRadius: "4px",
                          flex: 1,
                        }}
                      />
                      <button
                        onClick={() => handleOverride(item.id)}
                        style={{
                          padding: "0.25rem 0.5rem",
                          background: "#2563eb",
                          color: "#fff",
                          border: "none",
                          borderRadius: "4px",
                          cursor: "pointer",
                        }}
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setOverrideField(null)}
                        style={{
                          padding: "0.25rem 0.5rem",
                          background: "#9ca3af",
                          color: "#fff",
                          border: "none",
                          borderRadius: "4px",
                          cursor: "pointer",
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{ marginTop: "1rem", color: "#6b7280" }}>
        {total} pending item{total !== 1 ? "s" : ""}
      </p>
    </div>
  );
};
