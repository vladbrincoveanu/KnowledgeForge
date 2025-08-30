import React, { useRef, useState } from 'react';
import Papa from 'papaparse';
import './FileUploader.css';

const FileUploader = ({ onFilesUploaded, isProcessing }) => {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = async (fileList) => {
    const supportedFiles = Array.from(fileList).filter(file => 
      file.type === 'text/csv' || 
      file.name.endsWith('.csv') ||
      file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
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
        
        // Upload file to backend
        const uploadResult = await uploadFileToBackend(file);
        
        if (uploadResult.success) {
          processedFiles.push({
            name: file.name,
            headers: uploadResult.data.headers || [],
            data: uploadResult.data.data || [],
            size: file.size,
            collectionName: uploadResult.data.collection_name,
            rowCount: uploadResult.data.row_count
          });
          setUploadProgress(prev => ({ ...prev, [file.name]: 'success' }));
        } else {
          throw new Error(uploadResult.message || 'Upload failed');
        }
      } catch (error) {
        console.error(`Error processing ${file.name}:`, error);
        alert(`Error processing ${file.name}: ${error.message}`);
        setUploadProgress(prev => ({ ...prev, [file.name]: 'error' }));
      }
    }

    if (processedFiles.length > 0) {
      // Add new files to existing files instead of replacing
      const updatedFiles = [...uploadedFiles, ...processedFiles];
      setUploadedFiles(updatedFiles);
      onFilesUploaded(updatedFiles);
    }
  };

  const uploadFileToBackend = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/process/file', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  };



  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const clearFiles = () => {
    setUploadedFiles([]);
    setUploadProgress({});
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getFileIcon = (fileName) => {
    if (fileName.endsWith('.csv')) return '📊';
    if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) return '📈';
    return '📁';
  };

  const getProgressStatus = (fileName) => {
    const status = uploadProgress[fileName];
    switch (status) {
      case 'uploading':
        return <span className="status uploading">⏳ Uploading...</span>;
      case 'success':
        return <span className="status success">✅ Success</span>;
      case 'error':
        return <span className="status error">❌ Error</span>;
      default:
        return null;
    }
  };

  return (
    <div className="file-uploader">
      <h3>Upload Data Files</h3>
      
      <div 
        className={`upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleUploadClick}
      >
        <div className="upload-content">
          <div className="upload-icon">📁</div>
          <p>Drag and drop CSV or Excel files here or click to browse</p>
          <p className="upload-hint">Supports CSV, XLSX, and XLS files</p>
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
          <p>Analyzing file connections...</p>
        </div>
      )}
      
      {uploadedFiles.length > 0 && (
        <div className="upload-status">
          <p>📁 {uploadedFiles.length} file(s) uploaded</p>
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
                  <small>{file.headers.length} columns, {file.rowCount} rows</small>
                  {file.collectionName && (
                    <small className="collection-name">Collection: {file.collectionName}</small>
                  )}
                </div>
              </div>
              {getProgressStatus(file.name)}
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