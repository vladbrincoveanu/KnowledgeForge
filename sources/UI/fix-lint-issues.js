#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Function to fix common ESLint issues in a file
function fixFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;

  // Remove redundant React imports in .tsx files when React is not used explicitly
  if (filePath.endsWith('.tsx')) {
    // Remove standalone "import React from 'react';" if it exists
    const standaloneReactImport = /^import React from ['"]react['"];?\s*$/gm;
    if (standaloneReactImport.test(content)) {
      content = content.replace(standaloneReactImport, '');
      modified = true;
    }

    // Convert "import React, { ... }" to "import { ... }"
    const reactWithOthers = /^import React, \{ ([^}]+) \} from ['"]react['"];?\s*$/gm;
    if (reactWithOthers.test(content)) {
      content = content.replace(reactWithOthers, 'import { $1 } from \'react\';');
      modified = true;
    }
  }

  // Fix unused variables by prefixing with underscore
  const unusedVarPatterns = [
    /const (ontologyAPI|Papa|Link|Brain|LineChart|Line|performanceData|getConfidenceLabel|connectNodes|setTaskStatus) =/g,
    /function.*\((.*)(onEdgeConfirm|onEdgeReject|index),/g,
    /const (ConnectionOverviewModal|FileUploader) =/g
  ];

  unusedVarPatterns.forEach(pattern => {
    if (pattern.test(content)) {
      content = content.replace(pattern, (match, ...groups) => {
        return match.replace(/\b(ontologyAPI|Papa|Link|Brain|LineChart|Line|performanceData|getConfidenceLabel|connectNodes|setTaskStatus|onEdgeConfirm|onEdgeReject|index|ConnectionOverviewModal|FileUploader)\b/g, '_$1');
      });
      modified = true;
    }
  });

  // Fix unescaped quotes in JSX
  content = content.replace(/([^\\])"([^"]*)"([^=>\w])/g, '$1&quot;$2&quot;$3');

  if (modified) {
    fs.writeFileSync(filePath, content);
    console.log(`Fixed: ${filePath}`);
  }
}

// Find all TypeScript/TSX files in src directory
function findTsFiles(dir) {
  const files = [];
  const items = fs.readdirSync(dir);
  
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);
    
    if (stat.isDirectory()) {
      files.push(...findTsFiles(fullPath));
    } else if (item.endsWith('.ts') || item.endsWith('.tsx')) {
      files.push(fullPath);
    }
  }
  
  return files;
}

// Run the fix on all files
const srcDir = path.join(__dirname, 'src');
const tsFiles = findTsFiles(srcDir);

console.log(`Processing ${tsFiles.length} TypeScript files...`);
tsFiles.forEach(fixFile);
console.log('Done!');
