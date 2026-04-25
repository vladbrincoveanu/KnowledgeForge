import api from "./api";

export interface ReviewItem {
  id: string;
  extraction_run_id: string;
  field: string;
  candidate_values: string[];
  llm_suggestion: string | null;
  confidence: number;
  evidence: Array<{ type: string; source: string; snippet: string }>;
  status: string;
  reviewer_note: string | null;
  created_at: string;
  updated_at: string;
}

export const reviewService = {
  listPending: async (runId: string): Promise<{ items: ReviewItem[]; total: number }> => {
    const response = await api.get(`/v1/review/pending?run_id=${encodeURIComponent(runId)}`);
    return response.data;
  },

  approve: async (itemId: string, reviewerNote?: string): Promise<void> => {
    await api.post(`/v1/review/${itemId}/approve`, { reviewer_note: reviewerNote });
  },

  reject: async (itemId: string, reviewerNote?: string): Promise<void> => {
    await api.post(`/v1/review/${itemId}/reject`, { reviewer_note: reviewerNote });
  },

  override: async (itemId: string, value: string, reviewerNote?: string): Promise<void> => {
    await api.post(`/v1/review/${itemId}/override`, { value, reviewer_note: reviewerNote });
  },

  bulkApprove: async (runId: string, minConfidence = 0.85): Promise<void> => {
    await api.post(`/v1/review/${runId}/bulk-approve`, { min_confidence: minConfidence });
  },
};