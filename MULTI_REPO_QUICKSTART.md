# Multi-Repository Feature - Quick Start Guide

## 🚀 New Features Overview

### 1. Quick Add (Single Repository)
The simplest way to add one repository at a time:
```
┌─────────────────────────────────────┐
│ Extract Context                     │
├─────────────────────────────────────┤
│ [https://github.com/owner/repo   ] │
│ [Add Repository]                    │
└─────────────────────────────────────┘
```

### 2. Batch Input (Multiple URLs)
Add multiple repositories to a queue before extracting:
```
┌─────────────────────────────────────┐
│ Batch Input                         │
├─────────────────────────────────────┤
│ [URL Input          ] [Add]         │
│                                     │
│ Pending URLs:                       │
│ ┌─────────────────────────────┐   │
│ │ owner/repo-1           [×]   │   │
│ │ owner/repo-2           [×]   │   │
│ │ owner/repo-3           [×]   │   │
│ └─────────────────────────────┘   │
│                                     │
│ [Extract 3 Repositories]            │
└─────────────────────────────────────┘
```

### 3. GitHub Organization Scanner
Automatically fetch and extract all repos from a GitHub account:
```
┌─────────────────────────────────────┐
│ GitHub Account/Org                  │
├─────────────────────────────────────┤
│ [organization-name              ]   │
│                                     │
│ ┌─────────────────────────────┐   │
│ │ ☐ Include forks              │   │
│ │ Max repositories: [10 ▼]     │   │
│ └─────────────────────────────┘   │
│                                     │
│ [Scan organization-name Repos]      │
│                                     │
│ ℹ️ Limited to 60 repos/hour         │
└─────────────────────────────────────┘
```

---

## 💡 Usage Examples

### Example 1: Analyze Your Team's Microservices
```bash
1. Open CodeArchitectureViewer
2. Navigate to "Batch Input"
3. Add URLs:
   - https://github.com/myteam/auth-service
   - https://github.com/myteam/payment-service
   - https://github.com/myteam/user-service
   - https://github.com/myteam/notification-service
4. Click "Extract 4 Repositories"
5. Wait for sequential extraction
6. View complete system architecture
```

### Example 2: Scan an Open Source Organization
```bash
1. Open CodeArchitectureViewer
2. Navigate to "GitHub Account/Org"
3. Enter: "kubernetes"
4. Set: Max repositories = 10
5. Uncheck: "Include forks"
6. Click "Scan kubernetes Repositories"
7. GitHub API fetches top 10 repos
8. System extracts each automatically
9. View cumulative architecture graph
```

### Example 3: Quick Single Addition
```bash
1. Open CodeArchitectureViewer
2. Paste URL in quick add field
3. Press Enter or click "Add Repository"
4. Extraction starts immediately
5. Graph updates with new repository data
```

---

## 🎨 UI Improvements

### Before → After

#### Sidebar Width
```
Before: 220px (cramped)
After:  320px (comfortable)
```

#### Section Spacing
```
Before: 1.5rem between sections
After:  2rem between sections
```

#### Statistics Cards
```
Before:
┌─────────────┐
│ 15   Entities│
└─────────────┘

After:
┌─────────────┐
│     15      │
│  ENTITIES   │
└─────────────┘
(Larger numbers, better hierarchy)
```

#### Header
```
Before: White background, small text
After:  Purple gradient, white text, larger heading
```

---

## 🔧 Technical Details

### API Endpoints

#### Batch Extraction (Frontend-driven)
- Uses existing: `POST /api/v1/code/extract-from-github`
- Sequential calls for each URL
- Frontend manages progress tracking

#### Org Scanning (Backend-driven)
- New endpoint: `POST /api/v1/code/extract-from-github-org`
- Request body:
  ```json
  {
    "github_username": "organization-name",
    "include_forks": false,
    "max_repos": 10,
    "append_mode": true
  }
  ```
- Response: task_id for polling

### Data Accumulation
All extractions use `append_mode=true` by default:
- Data is **cumulative** across repositories
- Each new extraction adds to the graph
- Use "Clear All" to start fresh

---

## ⚠️ Important Notes

### GitHub API Rate Limits
- **60 requests/hour** for unauthenticated API
- Shared across your IP address
- Plan accordingly for large organizations

### Extraction Time
- Repositories are processed **sequentially**
- Average: 30-60 seconds per repository
- 10 repositories ≈ 5-10 minutes total

### Best Practices
1. **Start Small**: Test with 2-3 repos first
2. **Use Batch for Known URLs**: When you have specific repos
3. **Use Org Scanner for Discovery**: When exploring organizations
4. **Monitor Progress**: Watch status messages for errors
5. **Clear Periodically**: Reset data when switching contexts

---

## 🐛 Troubleshooting

### "GitHub API rate limit exceeded"
**Solution**: Wait until the next hour resets (GitHub shows time remaining in headers)

### "Repository not found"
**Solution**: Verify the URL is correct and the repository is public

### "Extraction failed"
**Solutions**:
- Check if repository is empty
- Verify repository has code (not just documentation)
- Try extracting again (transient network issues)

### Graph looks cluttered
**Solutions**:
- Use "Clear All" and extract fewer repositories
- Focus on specific domains or teams
- Use zoom controls to navigate large graphs

---

## 📊 Example Workflows

### Workflow 1: Microservices Analysis
```
Goal: Understand service dependencies
Steps:
1. Batch add all service repositories
2. Extract in one go
3. View relationships between services
4. Identify shared dependencies
5. Export architecture diagram
```

### Workflow 2: Open Source Exploration
```
Goal: Learn project structure
Steps:
1. Use org scanner for organization
2. Set max_repos = 5 (top projects)
3. Exclude forks to focus on originals
4. Extract and explore
5. Compare architectures across projects
```

### Workflow 3: Progressive Building
```
Goal: Build architecture incrementally
Steps:
1. Start with core service (quick add)
2. Add related services one by one
3. Observe graph growing
4. Identify gaps in architecture
5. Add missing services
```

---

## ✨ Pro Tips

### Tip 1: Keyboard Shortcuts
- Press **Enter** in URL input to add quickly
- Use **Tab** to navigate between fields

### Tip 2: URL Shortcuts
- Copy URLs directly from GitHub's address bar
- Works with `/tree/main`, `/blob/main`, etc.
- System extracts the base repository

### Tip 3: Organization Discovery
- Try variations: "facebook", "google", "microsoft"
- Exclude forks to reduce noise
- Start with max_repos = 5 for faster results

### Tip 4: Data Management
- Clear data between unrelated projects
- Keep extractions focused on one context
- Use descriptive repository names for clarity

---

## 🎯 Success Metrics

After implementation, users can:
- ✅ Add 10+ repositories in under 1 minute (batch)
- ✅ Scan entire GitHub orgs with 3 clicks
- ✅ View cumulative architecture across all repos
- ✅ Enjoy 45% more comfortable UI (320px vs 220px sidebar)
- ✅ See clearer visual hierarchy in statistics
- ✅ Track extraction progress in real-time

---

**Happy Architecting! 🏗️**
