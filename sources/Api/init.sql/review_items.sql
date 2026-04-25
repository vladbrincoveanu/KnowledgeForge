-- Review queue items table
CREATE TABLE IF NOT EXISTS review_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_run_id VARCHAR(255) NOT NULL,
    field VARCHAR(100) NOT NULL,
    candidate_values JSONB NOT NULL,
    llm_suggestion TEXT,
    confidence DECIMAL(3,2) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    reviewer_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_items_run_id ON review_items(extraction_run_id);
CREATE INDEX IF NOT EXISTS idx_review_items_status ON review_items(status);
