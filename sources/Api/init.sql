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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS recommendation_sessions (
    id UUID PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    phase VARCHAR(20) DEFAULT 'nodes',
    metadata JSONB,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE,
    nodes_approved_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS node_recommendations (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES recommendation_sessions(id),
    recommended_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4),
    reasoning TEXT,
    source_columns TEXT[],
    llm_metadata JSONB,
    user_feedback VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, recommended_name, entity_type)
);

CREATE TABLE IF NOT EXISTS edge_recommendations (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES recommendation_sessions(id),
    source_node_id UUID,
    target_node_id UUID,
    relationship_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4),
    reasoning TEXT,
    connection_evidence JSONB,
    user_feedback VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Migration scripts to handle existing databases
-- These operations are safe to run multiple times

-- Migration: Add unique constraint to node_recommendations to prevent duplicates
DO $$
BEGIN
    -- First, remove any existing duplicates before adding the constraint
    -- Keep only the first occurrence of each duplicate
    DELETE FROM node_recommendations a
    USING node_recommendations b
    WHERE a.id > b.id
    AND a.session_id = b.session_id
    AND a.recommended_name = b.recommended_name
    AND a.entity_type = b.entity_type;

    -- Now add the unique constraint if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'node_recommendations_session_name_type_unique'
    ) THEN
        ALTER TABLE node_recommendations
        ADD CONSTRAINT node_recommendations_session_name_type_unique
        UNIQUE (session_id, recommended_name, entity_type);
    END IF;
END $$;

-- Migration: Add phase tracking to recommendation_sessions table
DO $$
BEGIN
    -- Add the phase and nodes_approved_at columns if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'recommendation_sessions'
        AND column_name = 'phase'
    ) THEN
        ALTER TABLE recommendation_sessions
        ADD COLUMN phase VARCHAR(20) DEFAULT 'nodes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'recommendation_sessions'
        AND column_name = 'nodes_approved_at'
    ) THEN
        ALTER TABLE recommendation_sessions
        ADD COLUMN nodes_approved_at TIMESTAMP WITH TIME ZONE;
    END IF;

    -- Update existing records to have phase = 'nodes'
    UPDATE recommendation_sessions
    SET phase = 'nodes'
    WHERE phase IS NULL;
END $$;

-- Migration: Add updated_at column to extraction_runs table
DO $$
BEGIN
    -- Add the updated_at column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'extraction_runs'
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE extraction_runs
        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;

    -- Update existing records to have updated_at = created_at
    UPDATE extraction_runs
    SET updated_at = created_at
    WHERE updated_at IS NULL;
END $$;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_files_upload_timestamp ON files(upload_timestamp);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_file_id ON extraction_runs(file_id);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_status ON extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_user_feedback_entity_id ON user_feedback(entity_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_relationship_id ON user_feedback(relationship_id);
CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at ON system_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_task_id ON recommendation_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_status ON recommendation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_node_recommendations_session_id ON node_recommendations(session_id);
CREATE INDEX IF NOT EXISTS idx_edge_recommendations_session_id ON edge_recommendations(session_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE knowledgeforge TO knowledgeforge;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO knowledgeforge;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO knowledgeforge;
