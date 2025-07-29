import React, { useState, useCallback } from 'react';
import FileUploader from './components/FileUploader';
import Graph from './components/Graph';
import ConnectionPrompt from './components/ConnectionPrompt';
import './App.css';

function App() {
  const [files, setFiles] = useState([]);
  const [connections, setConnections] = useState([]);
  const [pendingConnection, setPendingConnection] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const findPotentialConnections = useCallback((headersA, headersB) => {
    const connections = [];
    
    headersA.forEach(headerA => {
      headersB.forEach(headerB => {
        const similarity = calculateSimilarity(headerA, headerB);
        if (similarity > 0.6) {
          connections.push({
            columnA: headerA,
            columnB: headerB,
            confidence: similarity
          });
        }
      });
    });
    
    return connections;
  }, []);

  // Mock LLM endpoint to check for semantic connections
  const checkSemanticConnections = useCallback(async (fileHeaders) => {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const potentialConnections = [];
    
    // Simple mock logic to find potential connections
    for (let i = 0; i < fileHeaders.length; i++) {
      for (let j = i + 1; j < fileHeaders.length; j++) {
        const fileA = fileHeaders[i];
        const fileB = fileHeaders[j];
        
        // Check for common patterns in column names
        const connections = findPotentialConnections(fileA.headers, fileB.headers);
        
        connections.forEach(connection => {
          potentialConnections.push({
            fileA: fileA.name,
            fileB: fileB.name,
            columnA: connection.columnA,
            columnB: connection.columnB,
            confidence: connection.confidence
          });
        });
      }
    }
    
    return potentialConnections;
  }, [findPotentialConnections]);

  const calculateSimilarity = (str1, str2) => {
    const normalize = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
    const norm1 = normalize(str1);
    const norm2 = normalize(str2);
    
    if (norm1 === norm2) return 1.0;
    if (norm1.includes(norm2) || norm2.includes(norm1)) return 0.8;
    if (norm1.includes('id') && norm2.includes('id')) return 0.7;
    if (norm1.includes('name') && norm2.includes('name')) return 0.7;
    if (norm1.includes('customer') && norm2.includes('customer')) return 0.9;
    if (norm1.includes('order') && norm2.includes('order')) return 0.9;
    
    return 0.0;
  };

  const handleFilesUploaded = useCallback(async (uploadedFiles) => {
    setFiles(uploadedFiles);
    setIsProcessing(true);
    
    try {
      // Extract headers from each file
      const fileHeaders = uploadedFiles.map(file => ({
        name: file.name,
        headers: file.headers
      }));
      
      // Check for semantic connections
      const potentialConnections = await checkSemanticConnections(fileHeaders);
      
      if (potentialConnections.length > 0) {
        setPendingConnection(potentialConnections[0]);
      }
    } catch (error) {
      console.error('Error processing files:', error);
    } finally {
      setIsProcessing(false);
    }
  }, [checkSemanticConnections]);

  const handleConnectionResponse = useCallback((accepted, connection) => {
    if (accepted) {
      setConnections(prev => [...prev, connection]);
    }
    
    // Remove the current pending connection
    setPendingConnection(null);
    
    // Check if there are more pending connections
    // This would be handled by the actual implementation
    // For now, we'll just clear the pending connection
  }, []);

  const graphData = {
    nodes: files.map(file => ({
      id: file.name,
      label: file.name,
      type: 'file'
    })),
    links: connections.map((connection, index) => ({
      id: `link-${index}`,
      source: connection.fileA,
      target: connection.fileB,
      label: `${connection.columnA} ↔ ${connection.columnB}`
    }))
  };

  return (
    <div className="app">
      <div className="container">
        <div className="header">
          <h1>KnowledgeForge Network Graph</h1>
          <p>Upload CSV files and discover connections between your data</p>
        </div>
        
        <div className="main-content">
          <div className="upload-section">
            <FileUploader 
              onFilesUploaded={handleFilesUploaded}
              isProcessing={isProcessing}
            />
            
            {files.length > 0 && (
              <div className="uploaded-files">
                <h3>Uploaded Files ({files.length})</h3>
                <ul>
                  {files.map((file, index) => (
                    <li key={index}>
                      <strong>{file.name}</strong>
                      <br />
                      <small>{file.headers.length} columns</small>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {connections.length > 0 && (
              <div className="connections">
                <h3>Connections ({connections.length})</h3>
                <ul>
                  {connections.map((connection, index) => (
                    <li key={index}>
                      <strong>{connection.fileA}</strong> ↔ <strong>{connection.fileB}</strong>
                      <br />
                      <small>{connection.columnA} ↔ {connection.columnB}</small>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          
          <div className="graph-section">
            <Graph data={graphData} />
          </div>
        </div>
        
        {pendingConnection && (
          <ConnectionPrompt
            connection={pendingConnection}
            onResponse={handleConnectionResponse}
          />
        )}
      </div>
    </div>
  );
}

export default App; 