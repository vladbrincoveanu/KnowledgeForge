import React, { useState } from 'react';
import './githuborgscanner.scss';

interface GitHubOrgScannerProps {
  onScanStart: (username: string, options: ScanOptions) => void;
  isScanning: boolean;
}

interface ScanOptions {
  includeForks: boolean;
  maxRepos: number;
}

const GitHubOrgScanner: React.FC<GitHubOrgScannerProps> = ({
  onScanStart,
  isScanning,
}) => {
  const [username, setUsername] = useState('venkataravuri');
  const [includeForks, setIncludeForks] = useState(false);
  const [maxRepos, setMaxRepos] = useState(10);
  const [inputError, setInputError] = useState('');

  // Helper function to extract username from GitHub URL or return username as-is
  const extractUsername = (input: string): string => {
    const trimmed = input.trim();
    
    // Handle various GitHub URL formats
    // https://github.com/username
    // http://github.com/username
    // github.com/username
    // @username
    // username
    
    const githubUrlPattern = /(?:https?:\/\/)?(?:www\.)?github\.com\/([^\/\s?#]+)/i;
    const match = trimmed.match(githubUrlPattern);
    
    if (match && match[1]) {
      return match[1]; // Extract username from URL
    }
    
    // Remove @ symbol if present
    if (trimmed.startsWith('@')) {
      return trimmed.substring(1);
    }
    
    return trimmed;
  };

  const handleScan = () => {
    const cleanUsername = extractUsername(username);
    
    if (!cleanUsername) {
      setInputError('Please enter a GitHub username or organization');
      return;
    }
    
    setInputError('');
    onScanStart(cleanUsername, { includeForks, maxRepos });
  };

  return (
    <div className="github-org-scanner">
      <div className="input-group">
        <input
          type="text"
          value={username}
          onChange={e => {
            setUsername(e.target.value);
            setInputError('');
          }}
          onKeyPress={e => e.key === 'Enter' && handleScan()}
          placeholder="username, @username or github.com/username"
          className="org-input"
        />
      </div>

      {inputError && <div className="error-text">{inputError}</div>}

      <div className="options">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeForks}
            onChange={e => setIncludeForks(e.target.checked)}
          />
          <span>Include forks</span>
        </label>

        <div className="max-repos-selector">
          <label>Max repositories:</label>
          <select
            value={maxRepos}
            onChange={e => setMaxRepos(Number(e.target.value))}
            className="max-repos-select"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={30}>30</option>
          </select>
        </div>
      </div>

      <button
        className="scan-button"
        onClick={handleScan}
        disabled={isScanning || !username.trim()}
      >
        Scan {username || 'Account'} Repositories
      </button>

      <div className="info-note">
        <small>ℹ️ Limited to 60 repos/hour (GitHub API)</small>
      </div>
    </div>
  );
};

export default GitHubOrgScanner;
