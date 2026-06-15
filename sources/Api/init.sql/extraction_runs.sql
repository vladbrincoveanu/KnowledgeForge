CREATE TABLE IF NOT EXISTS c4_extraction_runs (
    id VARCHAR(36) PRIMARY KEY,
    repo_url TEXT,
    repo_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    containers_count INTEGER NOT NULL DEFAULT 0,
    components_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_c4_extraction_runs_status ON c4_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_c4_extraction_runs_completed_at ON c4_extraction_runs(completed_at DESC);
