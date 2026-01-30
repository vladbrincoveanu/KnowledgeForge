# KnowledgeForge UI Enhancement: Multi-Repository Analysis & UI Polish

## Overview
Enhance the CodeArchitectureViewer to support batch GitHub repository analysis and improve overall UI spacing and graph visualization. This plan focuses on enabling users to input multiple GitHub URLs or an entire GitHub account to analyze all repositories in one cumulative graph view.

## User Requirements
1. **Batch URL Input**: Ability to add 2+ GitHub repository URLs and analyze them together
2. **GitHub Account Scanning**: Input a GitHub username/organization to fetch and analyze all public repositories
3. **UI Improvements**: Better spacing, layout, and graph visualization polish

## User Preferences (from clarification)
- **GitHub Authentication**: Unauthenticated API (60 requests/hour) - simpler, no token setup required
- **Default Repository Limit**: 10 repos (conservative, fast extraction)
- **UI Focus**: Spacing/layout improvements + Graph visualization polish

---

## Key Technical Context

### Current Architecture
- **Backend**: `/sources/Api/app/endpoint/v1/routes/code_extraction.py`
  - Endpoint: `POST /api/v1/code/extract-from-github`
  - **append_mode parameter**: Already supports cumulative multi-repo architecture
- **Frontend**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
  - Single GitHub URL input (lines 1215-1221)
  - Extraction handler with polling (lines 702-769)
  - Polls every 2 seconds for status updates
  - Applies architecture data on completion

### Multi-Repository Support Already Exists
The system **already supports** analyzing multiple repositories through the `append_mode=true` parameter (default). Each extraction adds to the cumulative architecture view stored in Neo4j and JSON files.

**Current UI hint** (line 1261): "💡 Data accumulates - add multiple repos to build complete architecture view"

---

## Implementation Plan

### Phase 1: Batch GitHub URL Input (Priority 1)

#### 1.1 Create BatchUrlInput Component
**New File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/batchurlinput.tsx`

**Purpose**: Allow users to add multiple GitHub URLs to a list before extracting

**Component Structure**:
```typescript
interface BatchUrlInputProps {
  onBatchExtract: (urls: string[]) => void;
  isExtracting: boolean;
}

interface UrlItem {
  id: string;
  url: string;
  status: 'pending' | 'extracting' | 'completed' | 'failed';
  progress?: number;
  error?: string;
}

const BatchUrlInput: React.FC<BatchUrlInputProps> = ({ onBatchExtract, isExtracting }) => {
  const [inputUrl, setInputUrl] = useState('');
  const [urlList, setUrlList] = useState<UrlItem[]>([]);
  const [inputError, setInputError] = useState('');

  const isValidGitHubUrl = (url: string): boolean => {
    return /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+/.test(url);
  };

  const handleAddUrl = () => {
    if (!isValidGitHubUrl(inputUrl)) {
      setInputError('Invalid GitHub URL');
      return;
    }
    if (urlList.some(item => item.url === inputUrl)) {
      setInputError('URL already added');
      return;
    }
    setUrlList([...urlList, {
      id: crypto.randomUUID(),
      url: inputUrl,
      status: 'pending'
    }]);
    setInputUrl('');
    setInputError('');
  };

  const handleRemoveUrl = (id: string) => {
    setUrlList(urlList.filter(item => item.id !== id));
  };

  const handleBatchExtract = () => {
    const pendingUrls = urlList
      .filter(item => item.status === 'pending')
      .map(item => item.url);
    onBatchExtract(pendingUrls);
  };

  return (
    <div className="batch-url-input">
      <div className="input-row">
        <input
          type="text"
          value={inputUrl}
          onChange={e => setInputUrl(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && handleAddUrl()}
          placeholder="https://github.com/owner/repo"
          className="url-input"
        />
        <button
          className="add-button"
          onClick={handleAddUrl}
          type="button"
        >
          Add
        </button>
      </div>

      {inputError && <div className="error-text">{inputError}</div>}

      {urlList.length > 0 && (
        <div className="url-list">
          {urlList.map(item => (
            <div key={item.id} className={`url-chip status-${item.status}`}>
              <span className="url-text" title={item.url}>
                {item.url.replace('https://github.com/', '')}
              </span>
              {item.status === 'extracting' && item.progress && (
                <span className="progress-text">{item.progress}%</span>
              )}
              {item.status === 'failed' && <span className="status-icon">❌</span>}
              {item.status === 'completed' && <span className="status-icon">✓</span>}
              {item.status === 'pending' && (
                <button
                  className="remove-btn"
                  onClick={() => handleRemoveUrl(item.id)}
                  type="button"
                  title="Remove"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {urlList.length > 0 && (
        <button
          className="batch-extract-btn"
          onClick={handleBatchExtract}
          disabled={urlList.filter(i => i.status === 'pending').length === 0 || isExtracting}
          type="button"
        >
          Extract {urlList.filter(i => i.status === 'pending').length} Repositories
        </button>
      )}
    </div>
  );
};

export default BatchUrlInput;
```

#### 1.2 Create BatchUrlInput Styles
**New File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/batchurlinput.scss`

**Design System Alignment**:
- Primary Blue: `#667eea`
- Success Green: `#22c55e`
- Error Red: `#ef4444`
- Border radius: `8px` (increased from 6px for more modern look)
- Spacing: 12px, 16px, 20px (4px grid with more breathing room)

```scss
.batch-url-input {
  display: flex;
  flex-direction: column;
  gap: 16px; // Increased from 12px

  .input-row {
    display: flex;
    gap: 12px;

    .url-input {
      flex: 1;
      padding: 12px 16px; // Increased from 8px 12px
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      font-size: 0.95rem;
      transition: all 0.2s;

      &:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      }
    }

    .add-button {
      padding: 12px 24px; // Increased padding
      background: #667eea;
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;

      &:hover {
        background: #5568d3;
      }
    }
  }

  .error-text {
    color: #ef4444;
    font-size: 0.85rem;
    margin-top: -8px;
  }

  .url-list {
    display: flex;
    flex-direction: column;
    gap: 10px; // Increased from 8px
    max-height: 240px; // Increased from 200px
    overflow-y: auto;
    padding: 2px; // Prevent scrollbar from cutting shadows
  }

  .url-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px; // Increased from 8px 12px
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 0.9rem;
    transition: all 0.2s;

    &.status-pending {
      border-left: 4px solid #94a3b8; // Increased from 3px
    }

    &.status-extracting {
      border-left: 4px solid #667eea;
      background: #f0f4ff;
    }

    &.status-completed {
      border-left: 4px solid #22c55e;
      background: #f0fdf4;
    }

    &.status-failed {
      border-left: 4px solid #ef4444;
      background: #fef2f2;
    }

    .url-text {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-right: 12px;
    }

    .progress-text {
      color: #667eea;
      font-weight: 600;
      font-size: 0.85rem;
      margin-right: 8px;
    }

    .status-icon {
      margin-right: 4px;
    }

    .remove-btn {
      background: none;
      border: none;
      color: #94a3b8;
      font-size: 1.75rem; // Larger for easier clicking
      cursor: pointer;
      padding: 0 4px;
      line-height: 1;
      transition: color 0.2s;

      &:hover {
        color: #ef4444;
      }
    }
  }

  .batch-extract-btn {
    padding: 14px 20px; // Increased padding
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);

    &:hover:not(:disabled) {
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
    }
  }
}
```

#### 1.3 Integrate BatchUrlInput into CodeArchitectureViewer
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

**Changes**:

1. **Import BatchUrlInput** (after line 20):
```typescript
import BatchUrlInput from './batchurlinput';
```

2. **Add batch state** (around line 60):
```typescript
const [batchUrls, setBatchUrls] = useState<Array<{id: string, url: string, status: string}>>([]);
const [currentBatchIndex, setCurrentBatchIndex] = useState(0);
```

3. **Add batch extraction handler** (after line 769):
```typescript
const handleBatchExtract = useCallback(async (urls: string[]) => {
  if (urls.length === 0) return;

  setIsExtracting(true);
  setExtractionError(null);
  setCurrentBatchIndex(0);

  // Sequential extraction to avoid overwhelming backend
  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    setCurrentBatchIndex(i + 1);
    setExtractionStatus(`Extracting ${i + 1}/${urls.length}: ${url.replace('https://github.com/', '')}`);

    try {
      const response = await codeArchitectureAPI.extractFromGitHub(url, true, true);
      const taskId = response.task_id;

      // Poll for completion
      let completed = false;
      while (!completed) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const status = await codeArchitectureAPI.getExtractionStatus(taskId);

        const progress = typeof status.progress === 'number'
          ? Math.round(status.progress * 100)
          : null;

        setExtractionStatus(
          `Extracting ${i + 1}/${urls.length}: ${url.replace('https://github.com/', '')} ${progress !== null ? `(${progress}%)` : ''}`
        );

        if (status.status === 'completed') {
          completed = true;
        } else if (status.status === 'failed') {
          throw new Error(status.message || 'Extraction failed');
        }
      }

    } catch (err) {
      console.error(`Failed on ${url}:`, err);
      setExtractionError(`Failed on ${url}: ${err instanceof Error ? err.message : 'Unknown error'}`);
      // Continue with remaining URLs
    }
  }

  setIsExtracting(false);
  setExtractionStatus(`Batch extraction completed - ${urls.length} repositories analyzed`);

  // Reload architecture data
  try {
    const data = await codeArchitectureAPI.getArchitecture();
    applyArchitecture(data);
    setSelectedLevel('context_level');
  } catch (err) {
    console.error('Failed to reload architecture:', err);
  }
}, [applyArchitecture]);
```

4. **Replace single URL input** (lines 1215-1221) with **BOTH options** - keep the simple single URL input AND add batch input below:
```tsx
<div className="filter-section">
  <h3>Extract Context</h3>

  {/* Single URL Quick Add */}
  <div className="quick-add-section">
    <input
      type="text"
      placeholder="https://github.com/owner/repo"
      value={githubUrl}
      onChange={e => setGithubUrl(e.target.value)}
      className="search-input"
      onKeyPress={e => e.key === 'Enter' && handleExtractFromGithub()}
    />
    <button
      className="fit-button"
      onClick={handleExtractFromGithub}
      disabled={isExtracting}
    >
      {isExtracting ? 'Extracting...' : 'Add Repository'}
    </button>
  </div>

  {/* Batch URL Input */}
  <div className="batch-section">
    <h4 className="subsection-title">Batch Input</h4>
    <BatchUrlInput
      onBatchExtract={handleBatchExtract}
      isExtracting={isExtracting}
    />
  </div>

  {/* Clear All Button */}
  <button
    className="reset-button"
    onClick={async () => {
      if (confirm('⚠️ Clear ALL repositories and start fresh? This will remove all accumulated architecture data.')) {
        try {
          await codeArchitectureAPI.clearArchitecture();
          setArchitecture(null);
          setNodes([]);
          setEdges([]);
          setGithubUrl('');
          setExtractionStatus('All repositories cleared - ready for fresh extraction');
          setExtractionError('');
        } catch (err) {
          setExtractionError('Failed to clear data');
        }
      }
    }}
    disabled={isExtracting}
    title="Clear all repositories and start fresh"
  >
    Clear All
  </button>

  {/* Status messages */}
  {extractionStatus && (
    <div className="extract-status">{extractionStatus}</div>
  )}
  {extractionError && (
    <div className="extract-error">{extractionError}</div>
  )}
  {architecture && (
    <div className="extract-info">
      <small>💡 Data accumulates - add multiple repos to build complete architecture view</small>
    </div>
  )}
</div>
```

---

### Phase 2: GitHub Account/Organization Scanning (Priority 2)

#### 2.1 Backend: GitHub API Integration
**File**: `/sources/Api/app/endpoint/v1/routes/code_extraction.py`

**Add after line 268** (after `extract_from_github` endpoint):

```python
class GitHubOrgScanRequest(BaseModel):
    """Request to scan all repositories from a GitHub user/organization."""
    github_username: str = Field(..., description="GitHub username or organization name")
    include_forks: bool = Field(default=False, description="Include forked repositories")
    max_repos: int = Field(default=10, description="Maximum repositories to scan")
    append_mode: bool = Field(default=True, description="Append to existing data")


@router.post("/extract-from-github-org", response_model=ScanResponse)
async def extract_from_github_org(
    request: GitHubOrgScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Fetch all public repositories from a GitHub user/org and extract them.

    Note: Unauthenticated GitHub API has 60 requests/hour limit.
    """
    import requests

    # Fetch repos from GitHub API (unauthenticated)
    repos_url = f'https://api.github.com/users/{request.github_username}/repos'
    params = {
        'type': 'all',
        'sort': 'updated',
        'per_page': min(request.max_repos, 100),
    }

    try:
        response = requests.get(repos_url, params=params, timeout=10)
        response.raise_for_status()
        repos = response.json()

        # Filter out forks if requested
        if not request.include_forks:
            repos = [r for r in repos if not r.get('fork', False)]

        # Limit to max_repos
        repos = repos[:request.max_repos]

        if not repos:
            raise HTTPException(
                status_code=404,
                detail=f"No repositories found for '{request.github_username}'"
            )

        # Create batch task
        task_id = str(uuid.uuid4())
        repo_urls = [r['html_url'] for r in repos]

        scan_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0.0,
            'message': f'Found {len(repo_urls)} repositories',
            'created_at': datetime.now(),
            'total_repos': len(repo_urls),
            'completed_repos': 0,
            'repo_urls': repo_urls,
            'errors': [],
        }

        # Queue batch extraction
        background_tasks.add_task(
            run_batch_extraction,
            task_id,
            repo_urls,
            request.append_mode,
        )

        return ScanResponse(
            task_id=task_id,
            status='pending',
            message=f'Queued {len(repo_urls)} repositories for extraction',
            created_at=datetime.now(),
        )

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"GitHub user/org '{request.github_username}' not found"
            )
        elif e.response.status_code == 403:
            raise HTTPException(
                status_code=429,
                detail="GitHub API rate limit exceeded (60/hour). Please try again later."
            )
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")


async def run_batch_extraction(task_id: str, repo_urls: list[str], append_mode: bool):
    """Background task to extract multiple repositories sequentially."""
    import shutil

    total = len(repo_urls)

    for idx, repo_url in enumerate(repo_urls):
        try:
            scan_tasks[task_id]['message'] = f'Extracting {idx + 1}/{total}: {repo_url}'
            scan_tasks[task_id]['progress'] = idx / total
            scan_tasks[task_id]['completed_repos'] = idx

            # Download repository
            temp_dir = Path(tempfile.mkdtemp(prefix=f"batch_{task_id}_{idx}_"))
            repo_path = GitHubDownloader.download_repository(
                repo_url,
                output_dir=temp_dir,
                use_git=True
            )

            # Run extraction
            await run_c4_extraction(
                task_id=f"{task_id}_repo_{idx}",
                repo_path=repo_path,
                append_mode=append_mode,
            )

            scan_tasks[task_id]['completed_repos'] = idx + 1

            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Failed to extract {repo_url}: {e}")
            scan_tasks[task_id].setdefault('errors', []).append({
                'repo_url': repo_url,
                'error': str(e),
            })

    scan_tasks[task_id]['status'] = 'completed'
    scan_tasks[task_id]['progress'] = 1.0
    scan_tasks[task_id]['message'] = f'Completed {total} repositories'
```

#### 2.2 Frontend: GitHub Org Scanner Component
**New File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/githuborgscanner.tsx`

```typescript
import React, { useState } from 'react';

interface GitHubOrgScannerProps {
  onScanStart: (username: string, options: ScanOptions) => void;
  isScanning: boolean;
}

interface ScanOptions {
  includeForks: boolean;
  maxRepos: number;
}

const GitHubOrgScanner: React.FC<GitHubOrgScannerProps> = ({ onScanStart, isScanning }) => {
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
```

#### 2.3 GitHub Org Scanner Styles
**New File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/githuborgscanner.scss`

```scss
.github-org-scanner {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .input-group {
    display: flex;

    .org-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      font-size: 0.95rem;
      transition: all 0.2s;

      &:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      }
    }
  }

  .error-text {
    color: #ef4444;
    font-size: 0.85rem;
    margin-top: -8px;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 0.9rem;

      input[type="checkbox"] {
        width: 16px;
        height: 16px;
        cursor: pointer;
      }
    }

    .max-repos-selector {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.9rem;

      label {
        font-weight: 500;
      }

      .max-repos-select {
        padding: 6px 12px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        background: white;
        cursor: pointer;

        &:focus {
          outline: none;
          border-color: #667eea;
        }
      }
    }
  }

  .scan-button {
    padding: 14px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);

    &:hover:not(:disabled) {
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
    }
  }

  .info-note {
    text-align: center;
    color: #64748b;
    font-size: 0.85rem;
  }
}
```

#### 2.4 API Service Layer Update
**File**: `/sources/UI/src/services/api.ts`

**Add method to codeArchitectureAPI** (after line 749):

```typescript
extractFromGitHubOrg: async (
  username: string,
  includeForks: boolean = false,
  maxRepos: number = 10,
  appendMode: boolean = true
): Promise<ExtractResponse> => {
  try {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      '/api/v1/code/extract-from-github-org',
      {
        github_username: username,
        include_forks: includeForks,
        max_repos: maxRepos,
        append_mode: appendMode,
      }
    );
    return response.data;
  } catch (error) {
    console.error('Failed to scan GitHub org:', error);
    throw error;
  }
},
```

#### 2.5 Integrate GitHub Org Scanner into CodeArchitectureViewer
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

**Changes**:

1. **Import component** (around line 22):
```typescript
import GitHubOrgScanner from './githuborgscanner';
```

2. **Add org scan handler** (after handleBatchExtract):
```typescript
const handleGitHubOrgScan = useCallback(async (
  username: string,
  options: { includeForks: boolean; maxRepos: number }
) => {
  setIsExtracting(true);
  setExtractionError(null);
  setExtractionStatus(`Scanning ${username} for repositories...`);

  try {
    const response = await codeArchitectureAPI.extractFromGitHubOrg(
      username,
      options.includeForks,
      options.maxRepos,
      true // append_mode
    );

    const taskId = response.task_id;

    // Poll for batch completion
    const pollInterval = setInterval(async () => {
      try {
        const status = await codeArchitectureAPI.getExtractionStatus(taskId);

        const progress = typeof status.progress === 'number'
          ? Math.round(status.progress * 100)
          : null;

        const completed = (status as any).completed_repos || 0;
        const total = (status as any).total_repos || options.maxRepos;

        setExtractionStatus(
          `Extracting ${completed}/${total} repositories... ${progress !== null ? `(${progress}%)` : ''}`
        );

        if (status.status === 'completed') {
          clearInterval(pollInterval);
          setIsExtracting(false);
          setExtractionStatus(`GitHub org scan completed - ${total} repositories analyzed`);

          // Reload architecture
          const data = await codeArchitectureAPI.getArchitecture();
          applyArchitecture(data);
          setSelectedLevel('context_level');

        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          setIsExtracting(false);
          setExtractionError(status.message || 'GitHub org scan failed');
        }
      } catch (pollError) {
        clearInterval(pollInterval);
        setIsExtracting(false);
        setExtractionError('Failed to poll extraction status');
      }
    }, 3000); // Poll every 3 seconds for batch operations

  } catch (err) {
    setIsExtracting(false);
    const errorMessage = err instanceof Error ? err.message : 'Failed to scan GitHub organization';
    setExtractionError(errorMessage);
  }
}, [applyArchitecture]);
```

3. **Add org scanner section** in the Extract Context section (after batch section):
```tsx
{/* GitHub Organization Scanner */}
<div className="org-scan-section">
  <h4 className="subsection-title">GitHub Account/Org</h4>
  <GitHubOrgScanner
    onScanStart={handleGitHubOrgScan}
    isScanning={isExtracting}
  />
</div>
```

---

### Phase 3: UI Polish - Spacing & Layout (Priority 1)

#### 3.1 Sidebar Width & Spacing Improvements
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss`

**Key Changes**:

```scss
// Line 371 - Increase sidebar width
.filters-sidebar {
  width: 320px;  // was 220px - much more comfortable
  min-width: 320px;
  padding: 1.75rem; // was 1rem - increased breathing room
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0; // Controlled by filter-section margin

  .filter-section {
    margin-bottom: 2rem; // was 1.5rem - more separation

    h3 {
      margin: 0 0 1.25rem 0; // was 0.75rem
      font-size: 1rem; // was 0.9rem
      font-weight: 700; // was 600 - bolder
      color: #0f172a;
      letter-spacing: 0.025em;
      text-transform: uppercase;
      font-size: 0.85rem;
    }

    h4.subsection-title {
      margin: 1.5rem 0 1rem 0;
      font-size: 0.9rem;
      font-weight: 600;
      color: #475569;
    }
  }
}

// Viewer header spacing
.viewer-header {
  padding: 2rem 2.5rem; // was 1rem 1.5rem - much more generous
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;

  h2 {
    margin: 0 0 0.5rem 0; // was 0.25rem
    font-size: 1.75rem; // was 1.35rem - larger, more impactful
    font-weight: 700; // was 600
  }

  p {
    margin: 0;
    opacity: 0.95;
    font-size: 1rem; // was 0.9rem
    line-height: 1.6;
  }
}

// Node details panel spacing
.node-details-panel {
  width: 360px; // was 280px - more comfortable for content
  background: white;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;

  .panel-header {
    padding: 1.75rem 2rem; // was 1.25rem 1.5rem
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;

    h3 {
      margin: 0 0 0.5rem 0;
      font-size: 1.25rem; // was 1.1rem
      font-weight: 700;
      color: #0f172a;
    }
  }

  .panel-content {
    padding: 2rem; // was 1.5rem
    flex: 1;

    .detail-row {
      margin-bottom: 1.75rem; // was 1rem - more space between rows

      .detail-label {
        display: block;
        font-size: 0.85rem;
        font-weight: 700; // was 600
        color: #64748b;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }

      .detail-value {
        font-size: 0.95rem;
        color: #1e293b;
        line-height: 1.6;
      }
    }
  }
}

// Statistics cards spacing
.stats {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px; // was 8px

  .stat {
    display: flex;
    flex-direction: column;
    padding: 1.25rem; // was 0.5rem - much more generous
    background: white;
    border-radius: 10px; // was 4px - more rounded
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border-left: 4px solid #667eea; // was 3px
    transition: transform 0.2s, box-shadow 0.2s;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }

    .stat-value {
      font-size: 2rem; // was 1.5rem - much bolder
      font-weight: 700;
      color: #667eea;
      line-height: 1;
      margin-bottom: 0.5rem; // was 0.25rem
    }

    .stat-label {
      font-size: 0.85rem;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }
  }
}

// Button spacing and styling
.button-group {
  display: flex;
  flex-direction: column;
  gap: 12px; // was 8px
  margin-top: 12px;
}

.fit-button, .reset-button {
  padding: 12px 16px; // was 0.75rem 1rem
  border-radius: 8px; // was 6px
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  width: 100%;
}

.fit-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);

  &:hover:not(:disabled) {
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    box-shadow: none;
  }
}

.reset-button {
  background: white;
  color: #64748b;
  border: 2px solid #e2e8f0; // was 1px

  &:hover:not(:disabled) {
    background: #f8fafc;
    border-color: #667eea;
    color: #667eea;
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    background: #f1f5f9;
  }
}

// Status messages spacing
.extract-status, .extract-error, .extract-info {
  margin-top: 1rem;
  padding: 12px 16px; // was 0.75rem 1rem
  border-left: 4px solid; // was 3px
  border-radius: 6px;
  font-size: 0.9rem;
  line-height: 1.5;
}

.extract-status {
  background: #f0f4ff;
  border-color: #667eea;
  color: #334155;
}

.extract-error {
  background: #fef2f2;
  border-color: #ef4444;
  color: #b91c1c;
  font-weight: 500;
}

.extract-info {
  background: #f0f9ff;
  border-color: #667eea;
  color: #475569;

  small {
    font-size: 0.85rem;
    line-height: 1.6;
  }
}

// Input field spacing
.search-input {
  width: 100%;
  padding: 12px 16px; // was 8px 12px
  border: 1px solid #e2e8f0;
  border-radius: 8px; // was 6px
  font-size: 0.95rem;
  margin-bottom: 12px;
  transition: all 0.2s;

  &:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }
}
```

---

### Phase 4: UI Polish - Graph Visualization (Priority 1)

#### 4.1 Graph Container & Background
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss`

```scss
.graph-container {
  flex: 1;
  position: relative;
  background: linear-gradient(to bottom, #f8fafc 0%, #ffffff 100%);
  overflow: hidden;
}

// ReactFlow-specific styling
.react-flow {
  background: linear-gradient(to bottom, #f8fafc 0%, #ffffff 100%);
}

.react-flow__pane {
  cursor: grab;

  &:active {
    cursor: grabbing;
  }
}
```

#### 4.2 Node Styling Enhancements
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CustomNode.scss`

**Key improvements**:

```scss
.custom-node {
  background: white;
  border-radius: 12px; // was 10px - more rounded
  padding: 16px; // was 12px - more generous
  min-width: 200px;
  max-width: 300px;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.08),
    0 2px 8px rgba(0, 0, 0, 0.06),
    0 0 0 1px rgba(0, 0, 0, 0.04);
  border: 2px solid transparent;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;

  &:hover {
    border-color: #667eea;
    box-shadow:
      0 4px 12px rgba(102, 126, 234, 0.15),
      0 8px 24px rgba(102, 126, 234, 0.1);
    transform: translateY(-2px);
  }

  &.selected {
    border-color: #667eea;
    box-shadow:
      0 0 0 3px rgba(102, 126, 234, 0.2),
      0 4px 12px rgba(102, 126, 234, 0.3),
      0 8px 24px rgba(102, 126, 234, 0.2);
  }

  .node-header {
    display: flex;
    align-items: center;
    gap: 10px; // was 8px
    margin-bottom: 12px; // was 8px

    .node-icon {
      font-size: 1.5rem; // was 1.25rem
    }

    .node-name {
      font-size: 1rem; // was 0.95rem
      font-weight: 700; // was 600
      color: #0f172a;
      flex: 1;
      word-break: break-word;
    }
  }

  .node-metadata {
    display: flex;
    flex-direction: column;
    gap: 8px; // was 6px

    .metadata-row {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;

      .metadata-label {
        color: #64748b;
        font-weight: 600;
        min-width: 60px;
      }

      .metadata-value {
        color: #1e293b;
        flex: 1;
        word-break: break-word;
      }
    }
  }

  .node-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px; // was 8px

    .badge {
      padding: 4px 10px; // was 3px 8px
      border-radius: 6px; // was 4px
      font-size: 0.75rem;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }
}

// Container nodes (frames)
.container-node {
  background: rgba(255, 255, 255, 0.95);
  border: 2px dashed #cbd5e1; // was 1px
  border-radius: 16px; // was 12px - more rounded
  padding: 20px; // was 16px

  &.k8s-container {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.02);
  }

  .container-header {
    font-size: 1.1rem; // was 1rem
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 12px; // was 8px
    padding-bottom: 12px; // was 8px
    border-bottom: 2px solid #e2e8f0; // was 1px
  }
}
```

#### 4.3 Edge (Connection) Styling
**File**: `/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/C4Edge.scss` (if exists) or add to CodeArchitectureViewer.scss:

```scss
.react-flow__edge {
  &-path {
    stroke: #94a3b8;
    stroke-width: 2px; // was 1px
    transition: stroke 0.2s, stroke-width 0.2s;
  }

  &.selected {
    .react-flow__edge-path {
      stroke: #667eea;
      stroke-width: 3px;
    }
  }

  &:hover {
    .react-flow__edge-path {
      stroke: #667eea;
      stroke-width: 3px;
    }
  }

  .react-flow__edge-text {
    font-size: 0.75rem;
    font-weight: 600;
    fill: #475569;
  }
}

// Relationship type colors
.react-flow__edge {
  &.uses, &.calls {
    .react-flow__edge-path {
      stroke: #3b82f6; // Blue for API calls
    }
  }

  &.depends-on {
    .react-flow__edge-path {
      stroke: #8b5cf6; // Purple for dependencies
    }
  }

  &.contains {
    .react-flow__edge-path {
      stroke: #10b981; // Green for containment
    }
  }
}
```

---

## Critical Files for Implementation

### Must Modify:
1. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`**
   - Lines 1215-1263: Replace/augment extraction UI
   - After line 769: Add handleBatchExtract and handleGitHubOrgScan
   - Around line 20: Add imports

2. **`/sources/Api/app/endpoint/v1/routes/code_extraction.py`**
   - After line 268: Add extract_from_github_org endpoint and run_batch_extraction function

3. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.scss`**
   - Line 371: Increase sidebar width
   - Throughout: Update spacing, padding values

4. **`/sources/UI/src/services/api.ts`**
   - After line 749: Add extractFromGitHubOrg method

5. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CustomNode.scss`**
   - Throughout: Enhance node styling with better spacing, hover effects

### Must Create:
6. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/batchurlinput.tsx`** (NEW)
7. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/batchurlinput.scss`** (NEW)
8. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/githuborgscanner.tsx`** (NEW)
9. **`/sources/UI/src/@components/architecture-map/CodeArchitectureViewer/githuborgscanner.scss`** (NEW)

---

## Implementation Sequence

### Step 1: Batch URL Input (Priority 1)
1. Create `batchurlinput.tsx` component
2. Create `batchurlinput.scss` styles
3. Add `handleBatchExtract` to CodeArchitectureViewer.tsx
4. Integrate BatchUrlInput into extraction section
5. Test with 2-3 GitHub repos

### Step 2: UI Spacing & Layout Polish (Priority 1)
1. Update sidebar width in CodeArchitectureViewer.scss (320px)
2. Increase all padding values (headers, panels, sections)
3. Update button spacing and styling
4. Enhance statistics cards with more padding
5. Improve status message styling

### Step 3: Graph Visualization Polish (Priority 1)
1. Update CustomNode.scss with larger padding, rounded corners
2. Add hover effects to nodes (border color, shadow, transform)
3. Enhance edge styling (thicker strokes, colors by type)
4. Update graph background gradient
5. Improve container node styling

### Step 4: GitHub Org Scanning (Priority 2)
1. Add backend endpoint in code_extraction.py
2. Create GitHubOrgScanner component
3. Create githuborgscanner.scss
4. Add extractFromGitHubOrg to api.ts
5. Add handleGitHubOrgScan to CodeArchitectureViewer.tsx
6. Integrate GitHubOrgScanner into extraction section
7. Test with small GitHub org (5-10 repos)

### Step 5: Testing & Refinement
1. Test batch extraction with multiple URLs
2. Test GitHub org scanning with real accounts
3. Verify cumulative architecture view
4. Test Clear All functionality
5. Run `npm run fix-all` to format code
6. Run `make quick-check` to verify backend tests

---

## Verification Strategy

### Unit Tests
- BatchUrlInput: URL validation, duplicate detection, add/remove functionality
- GitHubOrgScanner: Input validation, options handling

### Integration Tests
- Backend `/extract-from-github-org`: Valid/invalid username, rate limits, fork filtering
- Frontend batch extraction: Multiple URLs, sequential processing, status updates

### E2E Tests
1. Add 3 repos via batch input → extract → verify cumulative graph
2. Scan GitHub org → verify repos extracted → check progress updates
3. Clear all → verify empty state

### Visual QA Checklist
- [ ] Sidebar width comfortable (320px vs 220px)
- [ ] All sections have generous padding
- [ ] Statistics cards visually distinct with larger numbers
- [ ] Buttons have clear disabled states
- [ ] Status messages well-spaced and readable
- [ ] Graph nodes have smooth hover effects
- [ ] Graph nodes properly sized with adequate padding
- [ ] Edges visible with appropriate thickness
- [ ] Overall layout feels spacious and modern

---

## Post-Implementation Commands

### After UI Changes:
```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI
npm run fix-all  # Format and lint
```

### After Backend Changes:
```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge
make quick-check  # Run E2E tests
```

### Development:
```bash
# Terminal 1 - Backend
cd sources/Api
python -m uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd sources/UI
npm start
```

---

## Risk Mitigation

### Risk: GitHub API Rate Limits (60 requests/hour)
**Mitigation**:
- Default to 10 repos max
- Show clear error message when rate limit hit
- Sequential extraction to avoid overwhelming API
- Note in UI: "Limited to 60 repos/hour"

### Risk: Long Extraction Times for Multiple Repos
**Mitigation**:
- Sequential extraction with clear progress updates
- Show "Extracting X/Y" status
- Allow user to see progress per repository

### Risk: UI Complexity with Many URLs
**Mitigation**:
- Max height 240px for URL list with scrolling
- Clear visual status per URL (pending/extracting/completed/failed)
- Remove button only for pending URLs

---

## Success Criteria

✅ Users can add multiple GitHub URLs and extract them in one batch
✅ Users can input a GitHub username/org and extract all repos (up to configured limit)
✅ UI has significantly improved spacing and breathing room
✅ Graph nodes are visually enhanced with better styling
✅ All extraction progress is clearly communicated
✅ Cumulative architecture view shows all added repositories
✅ Clear All functionality works with confirmation
✅ Code passes `npm run fix-all` and `make quick-check`

---

**Implementation Ready**: All components, styles, and integration points are fully specified. Follow the step-by-step sequence for smooth implementation.
