import React, { useRef, useState, useEffect, useCallback } from 'react';
import { ontologyAPI, fileAPI, wsService, apiUtils } from '@/services/api';
import { UploadedFile, IncrementalSummary } from '@/types';
import {
  Upload,
  FileText,
  Database,
  Brain,
  CheckCircle,
  AlertCircle,
  Clock,
} from 'lucide-react';
import RecommendationModal from '@/@components/recommendation-modal/RecommendationModal/RecommendationModal';
import './FileUploader.scss';

interface FileUploaderProps {
  onFilesUploaded: (files: UploadedFile[]) => void;
  isProcessing: boolean;
  onExtractionStarted: (taskId: string, file: UploadedFile) => void;
  showNotification: (
    message: string,
    type: 'success' | 'error' | 'info'
  ) => void;
}

interface ExtractionTask {
  taskId: string;
  fileName: string;
  status:
    | 'pending'
    | 'processing'
    | 'completed'
    | 'failed'
    | 'awaiting_recommendations_approval';
  message: string;
  progress?: number;
  createdAt: string;
  estimatedCompletion?: string;
  startedAt?: string;
  completedAt?: string;
  processingTime?: number;
  results?: unknown;
  error?: string;
  incrementalSummary?: IncrementalSummary;
}

interface ExtendedUploadedFile extends UploadedFile {
  serverPath: string | null;
}

type UploadProgressStatus = 'uploading' | 'success' | 'error';
type UploadProgress = Record<string, UploadProgressStatus>;

const FileUploader: React.FC<FileUploaderProps> = ({
  onFilesUploaded,
  isProcessing,
  onExtractionStarted,
  showNotification,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<ExtendedUploadedFile[]>(
    []
  );
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({});
  const [extractionTasks, setExtractionTasks] = useState<
    Record<string, ExtractionTask>
  >({});
  const [recommendationModal, setRecommendationModal] = useState<{
    isOpen: boolean;
    taskId: string | null;
  }>({ isOpen: false, taskId: null });
  const [extractionConfig, setExtractionConfig] = useState({
    confidence_threshold: 0.7,
    max_entities_per_column: 100,
    enable_semantic_similarity: true,
    enable_hierarchical_discovery: true,
  });

  const handleWebSocketMessage = useCallback(
    (data?: unknown) => {
      const wsData = data as {
        task_id?: string;
        status?: string;
        message?: string;
        progress?: number;
        timestamp?: string;
        incremental_summary?: IncrementalSummary;
      };

      if (!wsData?.task_id) {
        return;
      }

      const shouldOpenModal =
        wsData.status === 'awaiting_recommendations_approval';

      setExtractionTasks(prev => {
        const existingTask = prev[wsData.task_id!];

        const baseTask: ExtractionTask =
          existingTask ||
          ({
            taskId: wsData.task_id!,
            fileName: `Task ${wsData.task_id!.substring(0, 8)}...`,
            status: 'pending',
            message: wsData.message || 'Task update received',
            progress: wsData.progress ?? 0,
            createdAt: wsData.timestamp || new Date().toISOString(),
            incrementalSummary: wsData.incremental_summary,
          } as ExtractionTask);

        const updatedTask: ExtractionTask = {
          ...baseTask,
          status:
            (wsData.status as ExtractionTask['status']) || baseTask.status,
          message: wsData.message || baseTask.message,
          progress: wsData.progress ?? baseTask.progress,
          incrementalSummary:
            wsData.incremental_summary ?? baseTask.incrementalSummary,
        };

        return {
          ...prev,
          [wsData.task_id!]: updatedTask,
        };
      });

      if (shouldOpenModal) {
        setRecommendationModal({
          isOpen: true,
          taskId: wsData.task_id,
        });
      }
    },
    [setRecommendationModal]
  );

  // WebSocket connection for real-time updates
  useEffect(() => {
    wsService.connect();

    const handleConnected = () => console.log('WebSocket connected');
    const handleDisconnected = () => console.log('WebSocket disconnected');

    wsService.on('message', handleWebSocketMessage);
    wsService.on('connected', handleConnected);
    wsService.on('disconnected', handleDisconnected);

    return () => {
      wsService.off('message', handleWebSocketMessage);
      wsService.off('connected', handleConnected);
      wsService.off('disconnected', handleDisconnected);
    };
  }, [handleWebSocketMessage]);

  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = async (fileList: FileList) => {
    const supportedFiles = Array.from(fileList).filter(
      (file: File) =>
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

    const newFiles = supportedFiles.filter(
      (file: File) =>
        !uploadedFiles.some(uploaded => uploaded.name === file.name)
    );

    if (newFiles.length !== supportedFiles.length) {
      alert('Some files were duplicates and have been ignored.');
    }

    // Add new files to the list immediately to show them in the UI
    const newFilePlaceholders: ExtendedUploadedFile[] = newFiles.map(
      (file: File) => ({
        name: file.name,
        size: file.size,
        headers: [],
        data: [],
        type: file.type,
        rowCount: 0,
        serverPath: null,
      })
    );
    setUploadedFiles(prev => [...prev, ...newFilePlaceholders]);

    const successfullyProcessed: ExtendedUploadedFile[] = [];
    for (const file of newFiles) {
      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 'uploading' }));

        // First upload the file to the server
        const uploadResult = await fileAPI.uploadFile(file);

        if (!uploadResult.file_path) {
          throw new Error('File upload failed: no file path returned');
        }

        // Process file locally for display purposes
        const processedFile = await fileAPI.processLocalFile(file);
        (processedFile as ExtendedUploadedFile).serverPath =
          uploadResult.file_path;

        setUploadedFiles(prev =>
          prev.map(f =>
            f.name === file.name ? (processedFile as ExtendedUploadedFile) : f
          )
        );
        successfullyProcessed.push(processedFile as ExtendedUploadedFile);

        setUploadProgress(prev => ({ ...prev, [file.name]: 'success' }));

        // Start ontology extraction with the server file path
        await startOntologyExtraction(processedFile as ExtendedUploadedFile);
      } catch (error) {
        console.error(`Error processing ${file.name}:`, error);
        alert(`Error processing ${file.name}: ${(error as Error).message}`);
        setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
      }
    }

    if (successfullyProcessed.length > 0) {
      onFilesUploaded(successfullyProcessed);
    }
  };

  const startOntologyExtraction = async (file: ExtendedUploadedFile) => {
    try {
      // Start extraction task with the uploaded file path
      if (!file.serverPath) {
        throw new Error('File server path is not available');
      }
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
            progress: 0,
            createdAt:
              (extractionResult as any).created_at || new Date().toISOString(),
            estimatedCompletion:
              (extractionResult as any).estimated_completion || null,
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

  const pollExtractionStatus = async (taskId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const status = await ontologyAPI.getExtractionStatus(taskId);

        setExtractionTasks(prev => ({
          ...prev,
          [taskId]: {
            ...prev[taskId],
            status: status.status === 'running' ? 'processing' : status.status,
            message: status.message || prev[taskId].message,
            progress: status.progress || prev[taskId].progress || 0,
            startedAt: (status as any).started_at,
            completedAt: (status as any).completed_at,
            processingTime: (status as any).processing_time,
            results: status.result,
            error: (status as any).error,
          },
        }));

        // Stop polling if task is completed or failed
        if (
          status.status === 'completed' ||
          status.status === 'failed' ||
          status.status === 'awaiting_recommendations_approval'
        ) {
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

  const getFileIcon = (fileName: string) => {
    if (fileName.endsWith('.csv')) return '📊';
    if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) return '📈';
    return '📁';
  };

  const getProgressStatus = (fileName: string) => {
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

  const getExtractionStatus = (fileName: string) => {
    const task = Object.values(extractionTasks).find(
      t => t.fileName === fileName
    );
    if (!task) return null;

    const statusColors: Record<string, string> = {
      pending: '#ffc107',
      processing: '#007bff',
      completed: '#28a745',
      failed: '#dc3545',
      awaiting_recommendations_approval: '#17a2b8',
    };

    const statusIcons: Record<string, JSX.Element> = {
      pending: <Clock size={16} />,
      processing: <Database size={16} />,
      completed: <CheckCircle size={16} />,
      failed: <AlertCircle size={16} />,
      awaiting_recommendations_approval: <Brain size={16} />,
    };

    return (
      <div
        className="extraction-status"
        style={{ color: statusColors[task.status] }}
      >
        {statusIcons[task.status]}
        <span>
          {task.status === 'awaiting_recommendations_approval'
            ? 'Recommendations ready for review'
            : task.message}
        </span>
        {task.processingTime && <small>({task.processingTime}s)</small>}
        {task.incrementalSummary && (
          <small className="incremental-summary">
            Entities +{task.incrementalSummary.added_entities} · Δ
            {task.incrementalSummary.modified_entities} · -
            {task.incrementalSummary.deleted_entities} | Relationships +
            {task.incrementalSummary.added_relationships} · -
            {task.incrementalSummary.deleted_relationships}
          </small>
        )}
      </div>
    );
  };

  const updateExtractionConfig = (key: string, value: unknown) => {
    setExtractionConfig(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleRecommendationApprove = (approvedItems: any) => {
    console.log('Approved items:', approvedItems);
    setRecommendationModal({ isOpen: false, taskId: null });
  };

  const handleRecommendationReject = () => {
    console.log('Recommendations rejected');
    setRecommendationModal({ isOpen: false, taskId: null });
  };

  return (
    <div className="file-uploader">
      <RecommendationModal
        isOpen={recommendationModal.isOpen}
        onClose={() => setRecommendationModal({ isOpen: false, taskId: null })}
        onApprove={handleRecommendationApprove}
        onReject={handleRecommendationReject}
        taskId={recommendationModal.taskId || ''}
        showNotification={showNotification}
      />
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
