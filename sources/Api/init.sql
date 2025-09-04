-- KnowledgeForge Database Initialization Script

-- Create the knowledgeforge database if it doesn't exist
SELECT 'CREATE DATABASE knowledgeforge'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'knowledgeforge')\gexec

-- Connect to the knowledgeforge database
\c knowledgeforge;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create basic tables structure (if needed)
-- This can be expanded based on your requirements

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE knowledgeforge TO knowledgeforge;
