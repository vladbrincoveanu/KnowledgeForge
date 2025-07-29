import React, { useRef, useState } from 'react';
import Papa from 'papaparse';
import './FileUploader.css';

const FileUploader = ({ onFilesUploaded, isProcessing }) => {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);

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
    const csvFiles = Array.from(fileList).filter(file => 
      file.type === 'text/csv' || file.name.endsWith('.csv')
    );

    if (csvFiles.length === 0) {
      alert('Please select CSV files only.');
      return;
    }

    const processedFiles = [];
    const existingFileNames = uploadedFiles.map(file => file.name);

    for (const file of csvFiles) {
      // Check if file already exists
      if (existingFileNames.includes(file.name)) {
        alert(`File "${file.name}" is already uploaded.`);
        continue;
      }

      try {
        const result = await parseCSVFile(file);
        processedFiles.push({
          name: file.name,
          headers: result.headers,
          data: result.data,
          size: file.size
        });
      } catch (error) {
        console.error(`Error parsing ${file.name}:`, error);
        alert(`Error parsing ${file.name}. Please ensure it's a valid CSV file.`);
      }
    }

    if (processedFiles.length > 0) {
      // Add new files to existing files instead of replacing
      const updatedFiles = [...uploadedFiles, ...processedFiles];
      setUploadedFiles(updatedFiles);
      onFilesUploaded(updatedFiles);
    }
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
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="file-uploader">
      <h3>Upload CSV Files</h3>
      
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
          <p>Drag and drop CSV files here or click to browse</p>
          <p className="upload-hint">Supports multiple CSV files</p>
        </div>
      </div>
      
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".csv,text/csv"
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
          <p className="upload-hint">Drag and drop more CSV files to add them</p>
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