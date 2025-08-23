# KnowledgeForge UI

A modern, responsive React-based user interface for the KnowledgeForge ontology extraction service. This UI provides a comprehensive interface for uploading files, extracting ontologies, viewing results, and monitoring system performance.

## 🚀 Features

### ✅ Core Functionality
- **File Upload & Processing**: Drag-and-drop CSV file upload with real-time progress tracking
- **Ontology Extraction**: Configure and start AI-powered ontology extraction tasks
- **Results Visualization**: View extracted entities and relationships with confidence scores
- **Graph Visualization**: Interactive network graph showing data relationships
- **System Monitoring**: Real-time metrics, health checks, and performance monitoring
- **Feedback System**: Submit validation feedback for extracted entities and relationships

### 🔌 API Integration
- **Full API Coverage**: Integrates with all ontology extraction API endpoints
- **Real-time Updates**: WebSocket support for live extraction progress updates
- **Authentication**: API key-based authentication with secure request handling
- **Error Handling**: Comprehensive error handling and user feedback

### 🎨 Modern UI/UX
- **Responsive Design**: Mobile-first design that works on all devices
- **Material Design**: Clean, modern interface with smooth animations
- **Dark/Light Theme**: Adaptive theming based on system preferences
- **Accessibility**: WCAG compliant with keyboard navigation support

## 🛠️ Installation

### Prerequisites
- Node.js 16+ and npm
- KnowledgeForge API running on localhost:8000
- Neo4j database (optional, for full functionality)

### Setup
1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   Create a `.env` file in the UI directory:
   ```bash
   # API Configuration
   REACT_APP_API_URL=http://localhost:8000
   REACT_APP_API_KEY=test-api-key-12345
   
   # Development Settings
   REACT_APP_DEBUG=true
   REACT_APP_ENABLE_WEBSOCKET=true
   ```

3. **Start development server**:
   ```bash
   npm start
   ```

4. **Build for production**:
   ```bash
   npm run build
   ```

## 📱 Usage

### 1. Upload & Extract
- Navigate to the "Upload & Extract" tab
- Configure extraction parameters (confidence threshold, entity limits, etc.)
- Drag and drop CSV files or click to browse
- Monitor real-time extraction progress
- View extraction status and results

### 2. View Results
- Go to "Ontology Results" tab
- Browse extracted entities and relationships
- Filter and search through results
- Export data in JSON or CSV format
- Submit feedback on extraction quality

### 3. Graph Visualization
- Visit "Graph View" tab
- Interactive network graph of entities and relationships
- Zoom, pan, and explore data connections
- Click nodes and edges for detailed information

### 4. System Monitoring
- Check "System Metrics" tab
- Monitor API health and performance
- View extraction statistics and quality metrics
- Real-time updates with configurable refresh intervals

### 5. Settings
- Configure API endpoints and authentication
- Set default extraction parameters
- Customize UI preferences and behavior

## 🔧 Configuration

### API Settings
```javascript
// Default API configuration
const API_CONFIG = {
  baseURL: 'http://localhost:8000',
  apiKey: 'your-api-key',
  timeout: 30000,
  enableWebSocket: true
};
```

### Extraction Parameters
```javascript
// Default extraction configuration
const EXTRACTION_CONFIG = {
  confidence_threshold: 0.7,
  max_entities_per_column: 100,
  enable_semantic_similarity: true,
  enable_hierarchical_discovery: true
};
```

### WebSocket Configuration
```javascript
// WebSocket settings for real-time updates
const WS_CONFIG = {
  reconnectAttempts: 5,
  reconnectDelay: 1000,
  heartbeatInterval: 30000
};
```

## 🏗️ Architecture

### Component Structure
```
src/
├── components/
│   ├── FileUploader.js          # File upload and extraction
│   ├── OntologyResults.js       # Results display and feedback
│   ├── Graph.js                 # Graph visualization
│   ├── SystemMetrics.js         # System monitoring
│   └── ConnectionPrompt.js      # Connection validation
├── services/
│   └── api.js                   # API integration layer
├── App.js                       # Main application
└── index.js                     # Entry point
```

### State Management
- **Local State**: Component-level state for UI interactions
- **API State**: Server state management with React Query
- **WebSocket State**: Real-time connection and message handling
- **Global State**: Application-wide state for navigation and user preferences

### Data Flow
1. **File Upload** → Local processing → API extraction request
2. **API Response** → Task tracking → Progress updates via WebSocket
3. **Results Loading** → Data fetching → UI rendering
4. **User Feedback** → API submission → Quality improvement

## 🔌 API Integration

### Endpoints Used
- `POST /extract` - Start ontology extraction
- `GET /extract/{task_id}` - Get extraction status
- `GET /entities` - Retrieve extracted entities
- `GET /relationships` - Retrieve discovered relationships
- `POST /feedback` - Submit user feedback
- `GET /graph/visualize` - Get graph visualization data
- `GET /metrics` - System performance metrics
- `GET /health` - API health check
- `GET /ready` - API readiness check
- `WS /ws` - Real-time updates

### Authentication
```javascript
// API key authentication
const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};
```

### Error Handling
```javascript
// Comprehensive error handling
try {
  const response = await api.post('/extract', data);
  return response.data;
} catch (error) {
  if (error.response?.status === 401) {
    // Handle authentication error
  } else if (error.response?.status === 429) {
    // Handle rate limiting
  } else {
    // Handle general errors
  }
}
```

## 🎨 Styling

### Design System
- **Color Palette**: Primary (#667eea), Success (#28a745), Warning (#ffc107), Error (#dc3545)
- **Typography**: System fonts with consistent sizing and weights
- **Spacing**: 8px grid system for consistent layouts
- **Shadows**: Subtle shadows for depth and hierarchy
- **Animations**: Smooth transitions and hover effects

### CSS Architecture
- **Component-based**: Each component has its own CSS file
- **Utility Classes**: Common patterns and responsive utilities
- **CSS Variables**: Theme-aware color and spacing variables
- **Responsive Design**: Mobile-first approach with breakpoints

## 📱 Responsive Design

### Breakpoints
```css
/* Mobile */
@media (max-width: 480px) { ... }

/* Tablet */
@media (max-width: 768px) { ... }

/* Desktop */
@media (max-width: 1024px) { ... }

/* Large Desktop */
@media (min-width: 1025px) { ... }
```

### Mobile Optimizations
- Touch-friendly interface elements
- Optimized layouts for small screens
- Swipe gestures for navigation
- Responsive tables and charts

## 🧪 Testing

### Test Commands
```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Generate coverage report
npm test -- --coverage

# Run specific test file
npm test -- FileUploader.test.js
```

### Test Coverage
- **Unit Tests**: Component logic and utility functions
- **Integration Tests**: API integration and data flow
- **E2E Tests**: User workflows and interactions
- **Accessibility Tests**: WCAG compliance and usability

## 🚀 Deployment

### Production Build
```bash
# Create optimized production build
npm run build

# Serve production build
npx serve -s build
```

### Docker Deployment
```bash
# Build Docker image
docker build -t knowledgeforge-ui .

# Run container
docker run -p 3000:80 knowledgeforge-ui
```

### Environment Variables
```bash
# Production environment
REACT_APP_API_URL=https://api.knowledgeforge.com
REACT_APP_API_KEY=production-api-key
REACT_APP_ENABLE_WEBSOCKET=true
```

## 🔒 Security

### Best Practices
- **API Key Management**: Secure storage and transmission
- **Input Validation**: Client-side validation for user inputs
- **HTTPS Only**: Secure communication in production
- **CORS Configuration**: Proper cross-origin request handling
- **Rate Limiting**: Client-side request throttling

### Authentication Flow
1. **API Key Storage**: Secure storage in environment variables
2. **Request Headers**: Automatic inclusion in all API calls
3. **Token Refresh**: Automatic retry on authentication failure
4. **Session Management**: Secure session handling and cleanup

## 📊 Performance

### Optimization Techniques
- **Code Splitting**: Lazy loading of components and routes
- **Bundle Optimization**: Tree shaking and minification
- **Image Optimization**: Responsive images and lazy loading
- **Caching**: Browser caching and service worker support
- **CDN Integration**: Static asset delivery optimization

### Monitoring
- **Performance Metrics**: Core Web Vitals tracking
- **Error Tracking**: Comprehensive error logging and reporting
- **User Analytics**: Usage patterns and feature adoption
- **API Performance**: Response time and success rate monitoring

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Code Standards
- **ESLint**: Code quality and consistency
- **Prettier**: Code formatting
- **TypeScript**: Type safety (optional)
- **Component Testing**: Unit and integration tests
- **Documentation**: Code comments and README updates

## 📚 Additional Resources

### Documentation
- [React Documentation](https://reactjs.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Recharts Documentation](https://recharts.org/)

### Related Projects
- [KnowledgeForge API](../Api/) - Backend API service
- [KnowledgeForge Core](../ontology_extractor/) - Core extraction logic
- [KnowledgeForge Docker](../docker/) - Containerization setup

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🆘 Support

### Getting Help
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Ask questions and share ideas
- **Documentation**: Comprehensive guides and examples
- **Community**: Join our developer community

### Contact
- **Email**: support@knowledgeforge.com
- **GitHub**: [KnowledgeForge Repository](https://github.com/knowledgeforge)
- **Discord**: [Community Server](https://discord.gg/knowledgeforge)

---

**Built with ❤️ by the KnowledgeForge Team**

