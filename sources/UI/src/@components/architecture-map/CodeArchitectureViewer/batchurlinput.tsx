import React, { useState } from 'react';
import './batchurlinput.scss';

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

const BatchUrlInput: React.FC<BatchUrlInputProps> = ({
  onBatchExtract,
  isExtracting,
}) => {
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
    setUrlList([
      ...urlList,
      {
        id: crypto.randomUUID(),
        url: inputUrl,
        status: 'pending',
      },
    ]);
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
        <button className="add-button" onClick={handleAddUrl} type="button">
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
              {item.status === 'failed' && (
                <span className="status-icon">❌</span>
              )}
              {item.status === 'completed' && (
                <span className="status-icon">✓</span>
              )}
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
          disabled={
            urlList.filter(i => i.status === 'pending').length === 0 ||
            isExtracting
          }
          type="button"
        >
          Extract {urlList.filter(i => i.status === 'pending').length}{' '}
          Repositories
        </button>
      )}
    </div>
  );
};

export default BatchUrlInput;
