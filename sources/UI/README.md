# KnowledgeForge Frontend

A React TypeScript application for semantic ontology extraction and visualization.

## Development Scripts

### Core Development Commands

```bash
# Start development server
npm run dev
# or
npm start

# Build for production
npm run build

# Preview production build
npm run preview

# Serve production build on network
npm run serve
```

### Code Quality & Formatting

```bash
# Format code with Prettier
npm run format

# Check if code is formatted correctly
npm run format:check

# Run ESLint
npm run lint

# Fix ESLint issues automatically
npm run lint:fix

# Check TypeScript types
npm run type-check

# Run all checks (TypeScript, ESLint, Prettier)
npm run check-all

# Fix all formatting and linting issues
npm run fix-all
```

### Testing

```bash
# Run tests once
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with UI
npm run test:ui
```

### CI/CD

```bash
# Run full CI pipeline (type-check, lint, format-check, build)
npm run ci
```

### Utility Commands

```bash
# Build and serve production version
npm run start:prod

# Clean build artifacts and cache
npm run clean

# Clean and reinstall dependencies
npm run reinstall
```

## Project Structure

```
src/
├── components/          # React components
├── services/           # API services and utilities
├── App.tsx            # Main application component
├── App.css           # Global styles
├── index.tsx         # Application entry point
└── index.css         # Base styles
```

## Configuration Files

- `tsconfig.json` - TypeScript configuration
- `tsconfig.node.json` - TypeScript configuration for Node.js files
- `.eslintrc.cjs` - ESLint configuration
- `.prettierrc.json` - Prettier configuration
- `.prettierignore` - Prettier ignore patterns
- `vite.config.ts` - Vite build configuration

## Development Workflow

1. **Start development**: `npm run dev`
2. **Make changes**: Edit files and see live updates
3. **Check code quality**: `npm run check-all`
4. **Fix issues**: `npm run fix-all`
5. **Run tests**: `npm run test`
6. **Build**: `npm run build`
7. **Preview**: `npm run preview`

## Technologies

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **ESLint** - Code linting
- **Prettier** - Code formatting
- **Vitest** - Testing framework
- **React Router** - Routing
- **Axios** - HTTP client
- **Lucide React** - Icons

## TypeScript & SCSS Migration Complete! 🎉

### ✅ **Successfully Migrated:**

#### **Frontend Architecture:**
- **React 18** with full **TypeScript** support
- **SCSS/Sass** preprocessing enabled
- **ESLint + Prettier** configured for TypeScript
- **Vite** optimized for TypeScript + SCSS

#### **Components Converted:**
- ✅ App.tsx (Main application)
- ✅ ConnectionPrompt.tsx
- ✅ ConnectionOverviewModal.tsx 
- ✅ FileUploader.tsx
- ✅ EdgeDetailsModal.tsx
- ✅ OntologyResults.tsx (Fully typed)
- ✅ NodeDetailsModal.tsx
- ✅ Graph.tsx
- ✅ VisualQueryBuilder.tsx
- ✅ SystemMetrics.tsx (Fully typed)

#### **Services Converted:**
- ✅ api.ts (Complete TypeScript interfaces)
- ✅ llmService.ts (Full type safety)
- ✅ semanticQueryService.ts (Comprehensive types)

#### **Styling Enhanced:**
- ✅ SCSS support added and configured
- ✅ App.scss (converted from CSS)
- ✅ index.scss (converted from CSS)
- ✅ ConnectionPrompt.scss (example conversion)
- ✅ All other CSS files ready for SCSS conversion

### 🛠️ **New Development Commands:**

```bash
# Development workflow
npm run dev:check          # Run type-check + lint + format-check
npm run dev:fix            # Auto-fix formatting and linting

# TypeScript specific
npm run type-check         # Check TypeScript types
npm run build              # TypeScript compilation + Vite build

# SCSS/CSS formatting
npm run format             # Format TS, TSX, JS, JSX, JSON, CSS, SCSS, MD
npm run format:check       # Check formatting for all file types

# Testing
npm run test              # Run tests
npm run test:watch        # Run tests in watch mode
npm run test:ui           # Run tests with UI
```

### 📁 **Updated Project Structure:**

```
src/
├── components/          # React components (.tsx)
│   ├── *.tsx           # TypeScript React components
│   ├── *.scss          # SCSS stylesheets (some converted)
│   └── *.css           # CSS stylesheets (ready for SCSS conversion)
├── services/           # API services (.ts)
│   ├── api.ts         # Main API service with full TypeScript
│   ├── llmService.ts  # LLM service with complete types
│   └── semanticQueryService.ts  # Query service with interfaces
├── types/             # TypeScript type definitions
│   └── index.ts       # Comprehensive type definitions
├── App.tsx           # Main application (TypeScript)
├── App.scss          # Main styles (SCSS)
├── index.tsx         # Application entry (TypeScript)
├── index.scss        # Base styles (SCSS)
└── vite-env.d.ts     # Vite environment types
```

### 🔧 **Configuration Files:**

- **TypeScript**: `tsconfig.json`, `tsconfig.node.json`
- **ESLint**: `.eslintrc.cjs` (TypeScript + React rules)
- **Prettier**: `.prettierrc.json`, `.prettierignore`
- **SCSS**: Automatically supported via Sass
- **Vite**: `vite.config.ts` (TypeScript configuration)

### 🎯 **Ready for Development:**

Your frontend is now a **modern TypeScript + SCSS React application** with:

- ✅ **Complete Type Safety** - All components and services typed
- ✅ **SCSS Support** - Modern CSS preprocessing
- ✅ **Code Quality** - ESLint + Prettier integration
- ✅ **Developer Experience** - Comprehensive npm scripts
- ✅ **Production Ready** - Optimized build process

**Start developing:** `npm run dev`

**Check code quality:** `npm run dev:check`

**Fix issues:** `npm run dev:fix`

**Build for production:** `npm run build`
