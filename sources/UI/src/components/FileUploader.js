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
        
        // Parse file locally to get sample data
        let sampleData = [];
        if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
          const parsedData = await parseCSVFile(file);
          sampleData = parsedData.data.slice(0, 5); // Get first 5 rows as sample
        }
        
        // Upload file to backend
        const uploadResult = await uploadFileToBackend(file);
        
        if (uploadResult.success) {
          // Transform backend response to match expected format
          const transformedFile = {
            name: file.name,
            label: uploadResult.data.collection_name || file.name.replace(/\.[^/.]+$/, ""), // Use collection name or filename without extension
            headers: uploadResult.data.file_info?.total_columns ? Array.from({length: uploadResult.data.file_info.total_columns}, (_, i) => `column_${i+1}`) : [],
            data: uploadResult.data.data || [],
            sampleData: sampleData, // Include sample data for metadata merging
            size: file.size,
            collectionName: uploadResult.data.collection_name,
            rowCount: uploadResult.data.file_info?.total_rows || 0,
            // Transform metadata to match expected format
            metadata: {
              columns: uploadResult.data.file_info?.total_columns ? 
                Object.keys(uploadResult.data.columns || {}).reduce((acc, colName) => {
                  acc[colName] = {
                    name: colName,
                    data_type: uploadResult.data.columns[colName]?.data_type || 'string',
                    nullable: uploadResult.data.columns[colName]?.nullable || false,
                    unique_count: uploadResult.data.columns[colName]?.unique_count || 0,
                    sample_values: uploadResult.data.columns[colName]?.sample_values || []
                  };
                  return acc;
                }, {}) : {}
            }
          };
          
          processedFiles.push(transformedFile);
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

    // Use the correct API base URL
    const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    
    const response = await fetch(`${API_BASE_URL}/process/file`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    console.log('Backend response for file upload:', result);
    return result;
  };

  const parseCSVFile = (file) => {
    return new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (results.errors.length > 0) {
            reject(new Error('CSV parsing errors'));
            return;
          }
          
          resolve({
            headers: results.meta.fields || [],
            data: results.data
          });
        },
        error: (error) => {
          reject(error);
        }
      });
    });
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