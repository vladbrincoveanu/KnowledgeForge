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
  const [username, setUsername] = useState('');
  const [includeForks, setIncludeForks] = useState(false);
  const [maxRepos, setMaxRepos] = useState(10);
  const [inputError, setInputError] = useState('');

  const handleScan = () => {
    if (!username.trim()) {
      setInputError('Please enter a GitHub username or organization');
      return;
    }
    setInputError('');
    onScanStart(username.trim(), { includeForks, maxRepos });
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
          placeholder="username or organization"
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
