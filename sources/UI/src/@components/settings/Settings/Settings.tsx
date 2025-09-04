import React, { useState } from 'react';
import { Settings as _SettingsIcon } from 'lucide-react';
import './Settings.scss';

interface SettingsConfig {
  apiBaseUrl: string;
  apiKey: string;
  confidenceThreshold: number;
  autoRefreshMetrics: boolean;
}

interface SettingsProps {
  onSettingsChange?: (settings: SettingsConfig) => void;
}

const Settings: React.FC<SettingsProps> = ({ onSettingsChange }) => {
  const [settings, setSettings] = useState<SettingsConfig>({
    apiBaseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    apiKey: import.meta.env.VITE_API_KEY || 'test-api-key-12345',
    confidenceThreshold: 0.7,
    autoRefreshMetrics: true,
  });

  const [isModified, setIsModified] = useState(false);

  const handleInputChange = (
    field: keyof SettingsConfig,
    value: string | number | boolean
  ) => {
    const newSettings = { ...settings, [field]: value };
    setSettings(newSettings);
    setIsModified(true);
  };

  const handleSave = () => {
    onSettingsChange?.(settings);
    setIsModified(false);
    // In a real app, you might want to show a success toast here
    console.log('Settings saved:', settings);
  };

  const handleReset = () => {
    setSettings({
      apiBaseUrl: 'http://localhost:8000',
      apiKey: 'test-api-key-12345',
      confidenceThreshold: 0.7,
      autoRefreshMetrics: true,
    });
    setIsModified(true);
  };

  return (
    <div className="settings-content">
      <div className="setting-group">
        <h3>API Configuration</h3>
        <div className="setting-item">
          <label htmlFor="api-base-url">API Base URL:</label>
          <input
            id="api-base-url"
            type="text"
            value={settings.apiBaseUrl}
            onChange={e => handleInputChange('apiBaseUrl', e.target.value)}
            placeholder="API base URL"
          />
        </div>
        <div className="setting-item">
          <label htmlFor="api-key">API Key:</label>
          <input
            id="api-key"
            type="password"
            value={settings.apiKey}
            onChange={e => handleInputChange('apiKey', e.target.value)}
            placeholder="API key"
          />
        </div>
      </div>

      <div className="setting-group">
        <h3>Extraction Settings</h3>
        <div className="setting-item">
          <label htmlFor="confidence-threshold">
            Default Confidence Threshold: {settings.confidenceThreshold}
          </label>
          <input
            id="confidence-threshold"
            type="range"
            min="0.1"
            max="1.0"
            step="0.1"
            value={settings.confidenceThreshold}
            onChange={e =>
              handleInputChange(
                'confidenceThreshold',
                parseFloat(e.target.value)
              )
            }
          />
        </div>
        <div className="setting-item">
          <label htmlFor="auto-refresh">
            <input
              id="auto-refresh"
              type="checkbox"
              checked={settings.autoRefreshMetrics}
              onChange={e =>
                handleInputChange('autoRefreshMetrics', e.target.checked)
              }
            />
            Auto-refresh Metrics
          </label>
        </div>
      </div>

      <div className="settings-actions">
        <button
          className="btn-reset-settings"
          onClick={handleReset}
          type="button"
        >
          Reset to Defaults
        </button>
        <button
          className="btn-save-settings"
          onClick={handleSave}
          disabled={!isModified}
          type="button"
        >
          Save Settings
        </button>
      </div>
    </div>
  );
};

export default Settings;
