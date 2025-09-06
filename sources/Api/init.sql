-- KnowledgeForge Database Initialization Script

-- Create the knowledgeforge database if it doesn't exist
SELECT 'CREATE DATABASE knowledgeforge'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'knowledgeforge')\gexec

-- Connect to the knowledgeforge database
\c knowledgeforge;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create metadata tables for KnowledgeForge
CREATE TABLE IF NOT EXISTS files (
    id VARCHAR(16) PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'uploaded',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id VARCHAR(36) PRIMARY KEY,
    file_id VARCHAR(16) REFERENCES files(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    entities_count INTEGER DEFAULT 0,
    relationships_count INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id VARCHAR(16) PRIMARY KEY,
    entity_id VARCHAR(255),
    relationship_id VARCHAR(255),
    feedback_type VARCHAR(50) NOT NULL,
    feedback_value TEXT,
    confidence_adjustment DECIMAL(3,2) DEFAULT 0.0,
    user_id VARCHAR(255),
    feedback_source VARCHAR(50) DEFAULT 'api',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value JSONB NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_files_upload_timestamp ON files(upload_timestamp);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_file_id ON extraction_runs(file_id);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_status ON extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_user_feedback_entity_id ON user_feedback(entity_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_relationship_id ON user_feedback(relationship_id);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE knowledgeforge TO knowledgeforge;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO knowledgeforge;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO knowledgeforge;
