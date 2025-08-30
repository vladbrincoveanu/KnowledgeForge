import React from 'react';

import { useRef, useState, useEffect, useCallback } from 'react';
import { ontologyAPI, fileAPI, wsService, apiUtils } from '../services/api';
import { UploadedFile } from '../types';
import {
  Upload,
  FileText,
  Database,
  Brain,
  CheckCircle,
  AlertCircle,
  Clock,
} from 'lucide-react';
import './FileUploader.css';

interface FileUploaderProps {
  onFilesUploaded: (files: UploadedFile[]) => void;
  isProcessing: boolean;
  onExtractionStarted: (taskId: string, file: UploadedFile) => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onFilesUploaded,
  isProcessing,
  onExtractionStarted,
}) => {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [extractionTasks, setExtractionTasks] = useState({});
  const [extractionConfig, setExtractionConfig] = useState({
    confidence_threshold: 0.7,
    max_entities_per_column: 100,
    enable_semantic_similarity: true,
    enable_hierarchical_discovery: true,
  });

  const handleWebSocketMessage = useCallback(
    data => {
      if (data.task_id && extractionTasks[data.task_id]) {
        setExtractionTasks(prev => ({
          ...prev,
          [data.task_id]: {
            ...prev[data.task_id],
            status: data.status,
            message: data.message,
            timestamp: data.timestamp,
          },
        }));
      }
    },
    [extractionTasks]
  );

  // WebSocket connection for real-time updates
  useEffect(() => {
    wsService.connect();

    wsService.on('message', handleWebSocketMessage);
    wsService.on('connected', () => console.log('WebSocket connected'));
    wsService.on('disconnected', () => console.log('WebSocket disconnected'));

    return () => {
      wsService.disconnect();
    };
  }, [handleWebSocketMessage]);

  const handleDrag = e => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = e => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleFileInput = e => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = async fileList => {
    const supportedFiles = Array.from(fileList).filter(
      file =>
        file.type === 'text/csv' ||
        file.name.endsWith('.csv') ||
        file.type ===
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
        file.name.endsWith('.xlsx') ||
        file.type === 'application/vnd.ms-excel' ||
        file.name.endsWith('.xls')
    );

    if (supportedFiles.length === 0) {
      alert('Please select CSV or Excel files only.');
      return;
    }

    const processedFiles = [];
    const existingFileNames = uploadedFiles.map(file => file.name);

    for (const file of supportedFiles) {
      // Check if file already exists
      if (existingFileNames.includes(file.name)) {
        alert(`File "${file.name}" is already uploaded.`);
        continue;
      }

      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 'uploading' }));

        // First upload the file to the server
        const uploadResult = await fileAPI.uploadFile(file);

        if (!uploadResult.file_path) {
          throw new Error('File upload failed: no file path returned');
        }

        // Process file locally for display purposes
        const processedFile = await fileAPI.processLocalFile(file);
        processedFile.serverPath = uploadResult.file_path; // Store server path
        processedFiles.push(processedFile);

        setUploadProgress(prev => ({ ...prev, [file.name]: 'success' }));

        // Start ontology extraction with the server file path
        await startOntologyExtraction(processedFile);
      } catch (error) {
        console.error(`Error processing ${file.name}:`, error);
        alert(`Error processing ${file.name}: ${error.message}`);
        setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
      }
    }

    if (processedFiles.length > 0) {
      const updatedFiles = [...uploadedFiles, ...processedFiles];
      setUploadedFiles(updatedFiles);
      onFilesUploaded(updatedFiles);
    }
  };

  const startOntologyExtraction = async file => {
    try {
      // Start extraction task with the uploaded file path
      const extractionResult = await ontologyAPI.extractOntology(
        file.serverPath,
        extractionConfig
      );

      if (extractionResult.task_id) {
        // Track the extraction task
        setExtractionTasks(prev => ({
          ...prev,
          [extractionResult.task_id]: {
            taskId: extractionResult.task_id,
            fileName: file.name,
            status: 'pending',
            message: 'Task created and queued',
            createdAt: extractionResult.created_at,
            estimatedCompletion: extractionResult.estimated_completion,
          },
        }));

        // Notify parent component
        if (onExtractionStarted) {
          onExtractionStarted(extractionResult.task_id, file);
        }

        // Start polling for status updates
        pollExtractionStatus(extractionResult.task_id);
      }
    } catch (error) {
      console.error('Failed to start ontology extraction:', error);
      throw error;
    }
  };

  const pollExtractionStatus = async taskId => {
    const pollInterval = setInterval(async () => {
      try {
        const status = await ontologyAPI.getExtractionStatus(taskId);

        setExtractionTasks(prev => ({
          ...prev,
          [taskId]: {
            ...prev[taskId],
            status: status.status,
            message: status.message,
            startedAt: status.started_at,
            completedAt: status.completed_at,
            processingTime: status.processing_time,
            results: status.results,
            error: status.error,
          },
        }));

        // Stop polling if task is completed or failed
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Failed to get extraction status:', error);
        clearInterval(pollInterval);
      }
    }, 2000); // Poll every 2 seconds
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const clearFiles = () => {
    setUploadedFiles([]);
    setUploadProgress({});
    setExtractionTasks({});
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getFileIcon = fileName => {
    if (fileName.endsWith('.csv')) return '📊';
    if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) return '📈';
    return '📁';
  };

  const getProgressStatus = fileName => {
    const status = uploadProgress[fileName];
    switch (status) {
      case 'uploading':
        return (
          <span className="status uploading">
            <Clock size={16} /> Uploading...
          </span>
        );
      case 'success':
        return (
          <span className="status success">
            <CheckCircle size={16} /> Success
          </span>
        );
      case 'error':
        return (
          <span className="status error">
            <AlertCircle size={16} /> Error
          </span>
        );
      default:
        return null;
    }
  };

  const getExtractionStatus = fileName => {
    const task = Object.values(extractionTasks).find(
      t => t.fileName === fileName
    );
    if (!task) return null;

    const statusColors = {
      pending: '#ffc107',
      processing: '#007bff',
      completed: '#28a745',
      failed: '#dc3545',
    };

    const statusIcons = {
      pending: <Clock size={16} />,
      processing: <Database size={16} />,
      completed: <CheckCircle size={16} />,
      failed: <AlertCircle size={16} />,
    };

    return (
      <div
        className="extraction-status"
        style={{ color: statusColors[task.status] }}
      >
        {statusIcons[task.status]}
        <span>{task.message}</span>
        {task.processingTime && <small>({task.processingTime}s)</small>}
      </div>
    );
  };

  const updateExtractionConfig = (key, value) => {
    setExtractionConfig(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <div className="file-uploader">
      <h3>
        <Upload size={20} /> Upload Data Files
      </h3>

      {/* Extraction Configuration */}
      <div className="extraction-config">
        <h4>
          <Brain size={16} /> Extraction Configuration
        </h4>
        <div className="config-grid">
          <div className="config-item">
            <label>Confidence Threshold:</label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.1"
              value={extractionConfig.confidence_threshold}
              onChange={e =>
                updateExtractionConfig(
                  'confidence_threshold',
                  parseFloat(e.target.value)
                )
              }
            />
            <span>{extractionConfig.confidence_threshold}</span>
          </div>

          <div className="config-item">
            <label>Max Entities per Column:</label>
            <input
              type="number"
              min="10"
              max="1000"
              value={extractionConfig.max_entities_per_column}
              onChange={e =>
                updateExtractionConfig(
                  'max_entities_per_column',
                  parseInt(e.target.value)
                )
              }
            />
          </div>

          <div className="config-item">
            <label>
              <input
                type="checkbox"
                checked={extractionConfig.enable_semantic_similarity}
                onChange={e =>
                  updateExtractionConfig(
                    'enable_semantic_similarity',
                    e.target.checked
                  )
                }
              />
              Enable Semantic Similarity
            </label>
          </div>

          <div className="config-item">
            <label>
              <input
                type="checkbox"
                checked={extractionConfig.enable_hierarchical_discovery}
                onChange={e =>
                  updateExtractionConfig(
                    'enable_hierarchical_discovery',
                    e.target.checked
                  )
                }
              />
              Enable Hierarchical Discovery
            </label>
          </div>
        </div>
      </div>

      <div
        className={`upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleUploadClick}
      >
        <div className="upload-content">
          <div className="upload-icon">
            <Upload size={48} />
          </div>
          <p>Drag and drop CSV or Excel files here or click to browse</p>
          <p className="upload-hint">Supports CSV, XLSX, and XLS files</p>
          <p className="upload-hint">
            Files will be processed for ontology extraction
          </p>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
        onChange={handleFileInput}
        style={{ display: 'none' }}
      />

      {isProcessing && (
        <div className="processing-indicator">
          <div className="spinner"></div>
          <p>Analyzing file connections and extracting ontology...</p>
        </div>
      )}

      {uploadedFiles.length > 0 && (
        <div className="upload-status">
          <p>
            <FileText size={16} /> {uploadedFiles.length} file(s) uploaded
          </p>
          <p className="upload-hint">Drag and drop more files to add them</p>
        </div>
      )}

      {uploadedFiles.length > 0 && (
        <div className="uploaded-files-list">
          {uploadedFiles.map((file, index) => (
            <div key={index} className="file-item">
              <div className="file-info">
                <span className="file-icon">{getFileIcon(file.name)}</span>
                <div className="file-details">
                  <strong>{file.name}</strong>
                  <small>
                    {file.headers.length} columns, {file.rowCount} rows
                  </small>
                  <small className="file-size">
                    {apiUtils.formatFileSize(file.size)}
                  </small>
                </div>
              </div>
              <div className="file-status">
                {getProgressStatus(file.name)}
                {getExtractionStatus(file.name)}
              </div>
            </div>
          ))}
        </div>
      )}

      {uploadedFiles.length > 0 && (
        <div className="upload-actions">
          <button
            className="btn-clear"
            onClick={clearFiles}
            disabled={isProcessing}
          >
            Clear All Files
          </button>
        </div>
      )}
    </div>
  );
};

export default FileUploader;
