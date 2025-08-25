# KnowledgeForge Frontend

A React application for visualizing CSV file connections using network graphs.

## Features

- **CSV File Upload**: Drag and drop or browse to upload multiple CSV files
- **Semantic Analysis**: Automatic detection of potential connections between file columns
- **Interactive Graph**: Visualize file relationships using react-force-graph
- **User Confirmation**: Confirm or reject suggested connections through a modal interface
- **Real-time Updates**: Graph updates dynamically as connections are established

## Getting Started

### Prerequisites

- Node.js (version 14 or higher)
- npm or yarn

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

4. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

## Usage

1. **Upload CSV Files**: Drag and drop CSV files into the upload area or click to browse
2. **Wait for Analysis**: The system will analyze file headers for potential connections
3. **Review Connections**: A modal will appear asking you to confirm potential connections
4. **Build the Graph**: As you confirm connections, the network graph will update in real-time

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── FileUploader.js      # CSV file upload component
│   │   ├── FileUploader.css
│   │   ├── Graph.js             # Network graph visualization
│   │   ├── Graph.css
│   │   ├── ConnectionPrompt.js   # Connection confirmation modal
│   │   └── ConnectionPrompt.css
│   ├── App.js                   # Main application component
│   ├── App.css
│   ├── index.js                 # Application entry point
│   └── index.css               # Global styles
├── package.json
└── README.md
```

## Dependencies

- **React**: UI framework
- **react-force-graph**: Network graph visualization
- **papaparse**: CSV file parsing
- **react-scripts**: Development and build tools

## Mock Backend

The application currently uses a mock LLM endpoint that simulates semantic analysis. In a real implementation, this would connect to an actual backend service.

## Available Scripts

- `npm start`: Runs the app in development mode
- `npm test`: Launches the test runner
- `npm run build`: Builds the app for production
- `npm run eject`: Ejects from Create React App (not recommended)

## Browser Support

The application works in all modern browsers that support ES6+ features. 