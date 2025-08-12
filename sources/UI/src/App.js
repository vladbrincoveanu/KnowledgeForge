import React, { useState, useCallback, useEffect } from 'react';
import FileUploader from './components/FileUploader';
import Graph from './components/Graph';
import ConnectionPrompt from './components/ConnectionPrompt';
import ConnectionOverviewModal from './components/ConnectionOverviewModal';
import llmService from './services/llmService';
import './App.css';

function App() {
  const [files, setFiles] = useState([]);
  const [connections, setConnections] = useState([]);
  const [pendingConnections, setPendingConnections] = useState([]);
  const [analyzedConnections, setAnalyzedConnections] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showOverviewModal, setShowOverviewModal] = useState(false);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  // API base URL - use relative path since nginx proxies /api/ to backend
  const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

  // Load initial graph data
  useEffect(() => {
    loadGraphData();
    loadPendingConnections();
  }, []);

  const loadGraphData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/connections/graph-data`);
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
        setFiles(data.nodes);
        setConnections(data.links);
      }
    } catch (error) {
      console.error('Error loading graph data:', error);
    }
  };

  const loadPendingConnections = async () => {
    try {
      // Clear any existing pending connections - we don't want them anymore
      setPendingConnections([]);
      setAnalyzedConnections([]);
      setShowOverviewModal(false);
      
      console.log('Pending connections system disabled - using new AI-powered approach');
    } catch (error) {
      console.error('Error clearing pending connections:', error);
    }
  };

  // NEW: Smart connection detection function (defined before usage to avoid TDZ)
  const detectSmartConnections = useCallback(async () => {
    try {
      console.log('Detecting smart connections between files...');
      const allFiles = files;
      console.log(`Analyzing ${allFiles.length} files for connections...`);
      console.log('Files:', allFiles);

      if (allFiles.length < 2) {
        console.log('Need at least 2 files for connection detection');
        return;
      }

      const filesWithMetadata = allFiles.filter(file => {
        const hasMetadata = file.metadata && file.metadata.columns;
        const hasHeaders = file.headers && file.headers.length > 0;
        console.log(`File ${file.label || file.name}: hasMetadata=${hasMetadata}, hasHeaders=${hasHeaders}, headers=${file.headers?.length || 0}, metadata=`, file.metadata);
        return hasMetadata || hasHeaders;
      });
      console.log(`Files with metadata or headers: ${filesWithMetadata.length}`);

      if (filesWithMetadata.length < 2) {
        console.log('Need at least 2 files with metadata or headers for connection detection');
        const fallbackConnections = [];
        for (let i = 0; i < allFiles.length; i++) {
          for (let j = i + 1; j < allFiles.length; j++) {
            const file1 = allFiles[i];
            const file2 = allFiles[j];
            fallbackConnections.push({
              id: `${file1.label || file1.name}_${file2.label || file2.name}`,
              source_collection: file1.label || file1.name,
              target_collection: file2.label || file2.name,
              source_column: 'id',
              target_column: 'id',
              confidence_score: 0.7,
              connection_type: 'foreign_key',
              created_at: new Date().toISOString(),
              status: 'pending'
            });
          }
        }
        if (fallbackConnections.length > 0) {
          setAnalyzedConnections(fallbackConnections);
          setShowOverviewModal(true);
          console.log(`✅ Showing ${fallbackConnections.length} fallback connections`);
          alert(`🎉 Found ${fallbackConnections.length} potential connections between your files! Check the modal to review them.`);
        }
        return;
      }

      const potentialConnections = [];
      for (let i = 0; i < filesWithMetadata.length; i++) {
        for (let j = i + 1; j < filesWithMetadata.length; j++) {
          const file1 = filesWithMetadata[i];
          const file2 = filesWithMetadata[j];
          const columns1 = Object.keys(file1.metadata?.columns || {}).length > 0 ? Object.keys(file1.metadata.columns) : (file1.headers || []);
          const columns2 = Object.keys(file2.metadata?.columns || {}).length > 0 ? Object.keys(file2.metadata.columns) : (file2.headers || []);
          console.log(`Analyzing ${file1.label || file1.name} (${columns1.length} columns) vs ${file2.label || file2.name} (${columns2.length} columns)`);
          console.log(`File1 columns: ${columns1.join(', ')}`);
          console.log(`File2 columns: ${columns2.join(', ')}`);
          for (const col1 of columns1) {
            for (const col2 of columns2) {
              if (isLogicalConnection(col1, col2, file1.label, file2.label)) {
                const confidence = calculateInitialConfidence(col1, col2, file1.label, file2.label);
                console.log(`✅ Found logical connection: ${col1} ↔ ${col2} (confidence: ${confidence})`);
                potentialConnections.push({
                  id: `${file1.label || file1.name}_${col1}_${file2.label || file2.name}_${col2}`,
                  source_collection: file1.label || file1.name,
                  target_collection: file2.label || file2.name,
                  source_column: col1,
                  target_column: col2,
                  confidence_score: confidence,
                  connection_type: 'foreign_key',
                  created_at: new Date().toISOString(),
                  status: 'pending'
                });
              }
            }
          }
        }
      }

      console.log(`Created ${potentialConnections.length} potential connections`);
      if (potentialConnections.length > 0) {
        const analyzed = await llmService.analyzeConnections(potentialConnections, 5);
        if (analyzed.length > 0) {
          setAnalyzedConnections(analyzed);
          setShowOverviewModal(true);
          console.log(`✅ Showing ${analyzed.length} smart connections in modal`);
          alert(`🎉 Found ${analyzed.length} smart connections between your files! Check the modal to review them.`);
        } else {
          console.log('No connections passed LLM analysis');
        }
      } else {
        console.log('No logical connections found between files');
        alert('🔍 No automatic connections found. Try clicking the "Detect Smart Connections" button manually.');
      }
    } catch (error) {
      console.error('Error detecting smart connections:', error);
    }
  }, [files]);

  const handleFilesUploaded = useCallback(async (uploadedFiles) => {
    console.log('Files uploaded:', uploadedFiles);
    setFiles(uploadedFiles);
    setIsProcessing(true);
    
    try {
      // Reload graph data after file upload
      await loadGraphData();
      
      // NEW: Smart connection detection using LLM
      if (Array.isArray(uploadedFiles) && uploadedFiles.length >= 2) {
        console.log('Starting smart connection detection...');
        // Show notification to user
        alert(`📁 ${uploadedFiles.length} files uploaded! Starting connection detection...`);
        // Wait a bit for state to update and then detect connections
        setTimeout(async () => {
          console.log('Triggering connection detection for', uploadedFiles.length, 'files');
          await detectSmartConnections();
        }, 2000); // Increased delay to ensure state is updated
      }
    } catch (error) {
      console.error('Error processing files:', error);
    } finally {
      setIsProcessing(false);
    }
  }, []); // Remove detectSmartConnections from dependencies to avoid circular dependency



  // New handlers for overview modal
  const handleConnectionAction = useCallback(async (connectionId, action) => {
    console.log(`Handling connection action: ${action} for connection ${connectionId}`);
    try {
      if (action === 'approve') {
        // Confirm the connection
        const response = await fetch(`${API_BASE_URL}/connections/confirm`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            potential_connection_id: connectionId,
            user_id: 'user',
            // Also send full connection payload for backend fallback
            connection: analyzedConnections.find(c => c.id === connectionId) ||
              pendingConnections.find(c => c.id === connectionId)
          })
        });

        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            console.log('Connection approved:', result.edge);
            // Reload graph data to show new edge
            await loadGraphData();
          }
        }
      }
      
      // Remove from both pending and analyzed connections
      setPendingConnections(prev => prev.filter(conn => conn.id !== connectionId));
      setAnalyzedConnections(prev => prev.filter(conn => conn.id !== connectionId));
      
    } catch (error) {
      console.error('Error handling connection action:', error);
    }
  }, []);

  const handleConfirmAll = useCallback(async (connectionIds) => {
    console.log(`Confirming all connections: ${connectionIds.length}`);
    try {
      // Confirm all selected connections
      const confirmPromises = connectionIds.map(connectionId =>
        fetch(`${API_BASE_URL}/connections/confirm`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            potential_connection_id: connectionId,
            user_id: 'user',
            connection: analyzedConnections.find(c => c.id === connectionId) ||
              pendingConnections.find(c => c.id === connectionId)
          })
        })
      );

      const responses = await Promise.all(confirmPromises);
      
      // Check if all confirmations were successful
      const successfulConfirmations = responses.filter(response => response.ok);
      console.log(`Successfully confirmed ${successfulConfirmations.length} connections`);
      
      // Remove confirmed connections from both lists
      setPendingConnections(prev => prev.filter(conn => !connectionIds.includes(conn.id)));
      setAnalyzedConnections(prev => prev.filter(conn => !connectionIds.includes(conn.id)));
      
      // Reload graph data to show new edges
      await loadGraphData();
      
      // Close overview modal if no more connections
      if (analyzedConnections.length <= connectionIds.length) {
        setShowOverviewModal(false);
      }
      
    } catch (error) {
      console.error('Error confirming all connections:', error);
    }
  }, [analyzedConnections.length]);

  const handleRejectAll = useCallback(async (connectionIds) => {
    console.log(`Rejecting all connections: ${connectionIds.length}`);
    try {
      // Remove rejected connections from both lists
      setPendingConnections(prev => prev.filter(conn => !connectionIds.includes(conn.id)));
      setAnalyzedConnections(prev => prev.filter(conn => !connectionIds.includes(conn.id)));
      
    } catch (error) {
      console.error('Error rejecting all connections:', error);
    }
  }, []);


  // Helper function to check if columns make logical sense
  const isLogicalConnection = (col1, col2, file1Name, file2Name) => {
    const col1Lower = col1.toLowerCase();
    const col2Lower = col2.toLowerCase();
    const file1Lower = file1Name.toLowerCase();
    const file2Lower = file2Name.toLowerCase();
    
    // Exact match
    if (col1Lower === col2Lower) return true;
    
    // Common identifier patterns
    const idPatterns = ['id', 'key', 'code', 'ref', 'num', 'no'];
    for (const pattern of idPatterns) {
      if (col1Lower.includes(pattern) && col2Lower.includes(pattern)) {
        const base1 = col1Lower.replace(pattern, '').replace(/[_-]/g, '');
        const base2 = col2Lower.replace(pattern, '').replace(/[_-]/g, '');
        if (base1 && base2 && (base1.includes(base2) || base2.includes(base1))) {
          return true;
        }
      }
    }
    
    // Semantic matches
    const semanticPairs = [
      ['customer', 'client'], ['user', 'customer'], ['order', 'purchase'],
      ['product', 'item'], ['date', 'created'], ['email', 'mail'],
      ['phone', 'telephone'], ['name', 'title'], ['price', 'cost']
    ];
    
    for (const [word1, word2] of semanticPairs) {
      if ((col1Lower.includes(word1) && col2Lower.includes(word2)) ||
          (col1Lower.includes(word2) && col2Lower.includes(word1))) {
        return true;
      }
    }
    
    return false;
  };

  // Helper function to calculate initial confidence
  const calculateInitialConfidence = (col1, col2, file1Name, file2Name) => {
    const col1Lower = col1.toLowerCase();
    const col2Lower = col2.toLowerCase();
    
    // Exact match gets highest confidence
    if (col1Lower === col2Lower) return 0.95;
    
    // ID patterns get high confidence
    const idPatterns = ['id', 'key', 'code'];
    for (const pattern of idPatterns) {
      if (col1Lower.includes(pattern) && col2Lower.includes(pattern)) {
        return 0.85;
      }
    }
    
    // Semantic matches get medium confidence
    const semanticPairs = [
      ['customer', 'client'], ['order', 'purchase'], ['product', 'item']
    ];
    
    for (const [word1, word2] of semanticPairs) {
      if ((col1Lower.includes(word1) && col2Lower.includes(word2)) ||
          (col1Lower.includes(word2) && col2Lower.includes(word1))) {
        return 0.75;
      }
    }
    
    return 0.6;
  };

  const handleOverviewClose = useCallback(() => {
    setShowOverviewModal(false);
  }, []);

  // Clear all data from MongoDB and reset state
  const clearAllData = useCallback(async () => {
    const confirmMessage = `⚠️ WARNING: This will permanently delete ALL data from the database including:
    
• All uploaded CSV/Excel files
• All detected connections
• All metadata and analysis results
• All cached data

This action cannot be undone. Are you sure you want to continue?`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    setIsProcessing(true);
    try {
      console.log('Clearing all data from MongoDB...');
      
      // Clear all collections from MongoDB
      const response = await fetch(`${API_BASE_URL}/clear-all-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Data cleared successfully:', result);
        
        // Reset all state to zero
        setFiles([]);
        setConnections([]);
        setPendingConnections([]);
        setAnalyzedConnections([]);
        setShowOverviewModal(false);
        setGraphData({ nodes: [], links: [] });
        
        alert('✅ All data has been cleared successfully!');
      } else {
        console.error('Failed to clear data');
        alert('❌ Failed to clear data. Please try again.');
      }
    } catch (error) {
      console.error('Error clearing data:', error);
      alert('❌ Error clearing data. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const handleEdgeClick = useCallback((edge) => {
    console.log('Edge clicked:', edge);
    // You can add additional edge click handling here
    // For example, opening a detailed view or triggering actions
  }, []);

  const handleEdgeConfirm = useCallback(async (edgeWithMetadata) => {
    try {
      console.log('Confirming edge with metadata:', edgeWithMetadata);
      
      // Call the API to confirm the connection
      const response = await fetch(`${API_BASE_URL}/connections/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          potential_connection_id: edgeWithMetadata.id,
          user_id: 'user', // In a real app, this would be the actual user ID
          corrected_metadata: edgeWithMetadata.corrected_metadata
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          console.log('Edge confirmed:', result.edge);
          
          // Reload graph data to include the new edge
          await loadGraphData();
          await loadPendingConnections();
        } else {
          console.error('Failed to confirm edge:', result.error);
        }
      } else {
        console.error('Error confirming edge');
      }
    } catch (error) {
      console.error('Error handling edge confirmation:', error);
    }
  }, []);

  const handleEdgeReject = useCallback(async (edgeId) => {
    try {
      console.log('Rejecting edge:', edgeId);
      
      // For now, we'll just remove it from the pending list
      // In a real implementation, you'd call an API to mark it as rejected
      setPendingConnections(prev => prev.filter(conn => conn.id !== edgeId));
      
      // Reload graph data
      await loadGraphData();
    } catch (error) {
      console.error('Error handling edge rejection:', error);
    }
  }, []);

  // Get the next pending connection to show
  const getNextPendingConnection = () => {
    return pendingConnections.length > 0 ? pendingConnections[0] : null;
  };

  const currentPendingConnection = getNextPendingConnection();
  
  console.log('Current pending connection:', currentPendingConnection);
  console.log('Pending connections count:', pendingConnections.length);

  return (
    <div className="App">
      {/* Visual Discovery Workflow Banner */}
      <div className="discovery-banner">
        <div className="banner-content">
          <div className="banner-icon">🎯</div>
          <div className="banner-text">
            <h2>AI-Powered Visual Knowledge Discovery</h2>
            <p>Upload your data files and let AI reveal hidden connections through interactive visual graphs. No SQL required.</p>
          </div>
          <div className="banner-steps">
            <div className="step-item">
              <span className="step-number">1</span>
              <span>Upload Files</span>
            </div>
            <div className="step-arrow">→</div>
            <div className="step-item">
              <span className="step-number">2</span>
              <span>AI Analysis</span>
            </div>
            <div className="step-arrow">→</div>
            <div className="step-item">
              <span className="step-number">3</span>
              <span>Visual Validation</span>
            </div>
            <div className="step-arrow">→</div>
            <div className="step-item">
              <span className="step-number">4</span>
              <span>Discover Insights</span>
            </div>
          </div>
        </div>
      </div>

      <div className="app-container">
        <div className="header">
          <div className="header-content">
            <div className="header-text">
              <h1>KnowledgeForge Network Graph</h1>
              <p>Upload CSV files and discover connections between your data</p>
            </div>
            <button 
              onClick={clearAllData}
              className="clear-all-btn"
              disabled={isProcessing}
              title="Clear all data from database"
              style={{
                backgroundColor: '#dc3545',
                color: 'white',
                padding: '10px 20px',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: 'bold',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                opacity: isProcessing ? 0.6 : 1,
                boxShadow: '0 2px 4px rgba(220,53,69,0.3)',
                transition: 'all 0.3s ease'
              }}
            >
              🗑️ Clear All Data
            </button>
          </div>
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
                      <strong>{file.label}</strong>
                      <br />
                      <small>
                        {file.metadata?.columns ? 
                          (typeof file.metadata.columns === 'object' ? 
                            Object.keys(file.metadata.columns).length : 
                            String(file.metadata.columns)
                          ) : 
                          (file.headers ? file.headers.length : 0)
                        } columns
                      </small>
                    </li>
                  ))}
                </ul>
                
                {files.length >= 2 && (
                  <div className="connection-actions">
                    <button 
                      onClick={detectSmartConnections}
                      className="detect-connections-btn"
                      disabled={isProcessing}
                      style={{
                        backgroundColor: '#007bff',
                        color: 'white',
                        padding: '12px 24px',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '16px',
                        fontWeight: 'bold',
                        cursor: isProcessing ? 'not-allowed' : 'pointer',
                        opacity: isProcessing ? 0.6 : 1,
                        boxShadow: '0 4px 8px rgba(0,123,255,0.3)',
                        transition: 'all 0.3s ease'
                      }}
                    >
                      🔍 Detect Smart Connections
                    </button>
                    <small style={{marginTop: '8px', display: 'block'}}>
                      Click to manually detect connections between your files
                    </small>
                    <br />
                    <small style={{color: '#dc3545', fontWeight: 'bold'}}>
                      {files.length} files uploaded - {files.filter(f => f.metadata?.columns || f.headers?.length > 0).length} with metadata
                    </small>
                    {analyzedConnections.length > 0 && (
                      <div style={{marginTop: '8px', padding: '8px', backgroundColor: '#d4edda', borderRadius: '4px', border: '1px solid #c3e6cb'}}>
                        <small style={{color: '#155724'}}>
                          ✅ {analyzedConnections.length} connections detected! Check the modal to review them.
                        </small>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            
            {connections.length > 0 && (
              <div className="connections">
                <h3>Confirmed Connections ({connections.length})</h3>
                <ul>
                  {connections.map((connection, index) => {
                    const safeLabel = (value) => {
                      if (value && typeof value === 'object') {
                        return value.label || value.id || 'Unknown';
                      }
                      return String(value ?? 'Unknown');
                    };
                    const sourceLabel = safeLabel(connection.source);
                    const targetLabel = safeLabel(connection.target);
                    const confidence = typeof connection.confidence === 'number' ? connection.confidence : 0.9;
                    return (
                      <li key={connection.id || index}>
                        <strong>{sourceLabel}</strong> ↔ <strong>{targetLabel}</strong>
                        <br />
                        <small>{connection.columnA} ↔ {connection.columnB}</small>
                        <br />
                        <small className={`confidence ${confidence >= 0.9 ? 'high' : confidence >= 0.7 ? 'medium' : 'low'}`}>
                          Confidence: {Math.round(confidence * 100)}%
                        </small>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}


          </div>
          
          <div className="graph-section">
            <Graph 
              data={graphData} 
              onEdgeClick={handleEdgeClick}
              onEdgeConfirm={handleEdgeConfirm}
              onEdgeReject={handleEdgeReject}
            />
          </div>
        </div>
        
        {/* AI-Powered Connection Overview Modal */}
        {showOverviewModal && analyzedConnections.length > 0 && (
          <ConnectionOverviewModal
            connections={analyzedConnections}
            onClose={handleOverviewClose}
            onConfirmAll={handleConfirmAll}
            onRejectAll={handleRejectAll}
            onConnectionAction={handleConnectionAction}
          />
        )}
      </div>
    </div>
  );
}

export default App; 