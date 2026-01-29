# Multi-Repository Support Implementation

## Summary
Fixed the architecture extraction system to support adding multiple GitHub repositories cumulatively, with proper owner detection from git data and LLM-enhanced project metadata.

## Issues Fixed

### 1. ✅ Data Reset on New Repository Addition
**Problem**: Adding a new repository would clear all existing architecture data.

**Solution**: 
- Updated `/architecture` endpoint to query Neo4j and return ALL stored data cumulatively
- Backend already had `append_mode` support - now properly utilized
- Neo4j stores all repositories' data persistently

**Changes**:
- `sources/Api/app/endpoint/v1/routes/code_extraction.py`: Updated `/architecture` endpoint (lines 570-685) to query Neo4j for cumulative data instead of serving static JSON file
- Endpoint now aggregates all systems, containers, components, and external dependencies from Neo4j

### 2. ✅ Owner Shows "Unknown" Instead of Git Contributors
**Problem**: Owner field displayed "Unknown" even when git contributor data was available.

**Solution**: Enhanced owner detection with multiple fallback strategies:
1. Check CODEOWNERS file
2. Check README for maintainer info
3. Use git contributors with LLM enrichment
4. Extract from top contributor's name/email
5. Use email domain as team name
6. Final fallback: top contributor email

**Changes**:
- `sources/Api/app/services/code_extraction/c4_extractor.py`: Enhanced `_detect_owner_team()` method (lines 1349-1391)
- Added git author name extraction
- Added more robust email domain parsing
- Changed default from "Unknown" to "Unassigned" for clarity

### 3. ✅ No LLM Enrichment for Project Name/Description
**Problem**: Project names were just directory names, and descriptions were missing or generic.

**Solution**: Added LLM enrichment for:
- **Project Name**: Uses LLM to generate descriptive 2-4 word names based on README content
- **System Purpose**: Already existed but enhanced with better README parsing
- **Owner/Team**: Enhanced with LLM suggestion from contributor patterns

**Changes**:
- `sources/Api/app/services/code_extraction/c4_extractor.py`: Enhanced `_detect_system_name()` method (lines 638-696)
  - Added LLM-based project name generation
  - Improved README parsing for titles
  - Better directory name cleanup as fallback
- Enhanced `_generate_system_purpose()` with better README extraction (lines 1181-1281)

### 4. ✅ Frontend Reset Issues
**Problem**: Frontend UI suggested data would reset and didn't clearly communicate cumulative behavior.

**Solution**: Updated UI messaging and clarity:
- Changed header to "Architecture Context (Multi-Repository)"
- Updated subtitle to explain cumulative behavior
- Enhanced "Clear All" confirmation message
- Added info text: "Data accumulates - add multiple repos to build complete architecture view"

**Changes**:
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`:
  - Updated viewer header (line 1151-1153)
  - Updated info message (line 1206)
  - Enhanced Clear All confirmation (line 1177)
  - Updated console logging for cumulative mode

## How It Works Now

### Adding Multiple Repositories

1. **First Repository**:
   ```
   User enters: https://github.com/company/repo1
   → Extraction creates: System, Containers, Components
   → Stored in Neo4j with append_mode=True (default)
   ```

2. **Second Repository**:
   ```
   User enters: https://github.com/company/repo2
   → Extraction creates: New System, Containers, Components
   → MERGED with existing data in Neo4j
   → UI shows combined view of both repositories
   ```

3. **Owner Detection Flow**:
   ```
   For each repository:
   1. Check CODEOWNERS → Found? Use it
   2. Check README → Found team mention? Use it
   3. Get git contributors → Use LLM to suggest team name
   4. Extract top contributor name/email
   5. Use email domain as fallback
   ```

4. **Project Name Flow**:
   ```
   For each repository:
   1. Check package.json/pyproject.toml → Found? Use it
   2. Check README title → Found? Use it
   3. Use LLM with README content → Generate descriptive name
   4. Clean up directory name → Fallback
   ```

### Data Accumulation

The `/architecture` endpoint now:
- Queries ALL systems from Neo4j
- Queries ALL containers from Neo4j
- Queries ALL components from Neo4j
- Queries ALL external dependencies
- Merges into single view: "Multi-Repository System"

### Clear All Functionality

The "Clear All" button:
- Deletes ALL nodes from Neo4j (System, Container, Component, ExternalService)
- Resets UI state
- Shows clear warning: "⚠️ Clear ALL repositories and start fresh?"

## Testing the Changes

### Test Scenario 1: Add Two GitHub Repositories
```bash
# 1. Start the services
make up

# 2. Navigate to UI: http://localhost:3000

# 3. Add first repository
#    Enter: https://github.com/username/repo1
#    Click: Add Repository
#    Wait for extraction to complete

# 4. Add second repository
#    Enter: https://github.com/username/repo2
#    Click: Add Repository
#    Wait for extraction to complete

# 5. Verify:
#    - Statistics show cumulative counts
#    - Both repositories' containers visible
#    - Owner field shows contributor name (not "Unknown")
#    - Project names are descriptive (LLM-generated)
```

### Test Scenario 2: Verify Owner Detection
```bash
# Check a repository with git history:
# - Should show top contributor name or team
# - Should NOT show "Unknown"
# - Check system context in diagram for owner field
```

### Test Scenario 3: Verify LLM Project Names
```bash
# Add a repository with README
# - Project name should be descriptive (not just dir name)
# - System purpose should be one-sentence summary
# - Owner should be determined from git/README
```

## Configuration

### LLM Settings
The system uses local LLM (LM Studio) for enrichment:
- Model: `Codestral-22B-v0.1-IQ3_M.gguf` (or configured model)
- Used for: Project names, system purpose, owner suggestions
- Fallbacks: Heuristic extraction if LLM unavailable

### Append Mode
By default, `append_mode=True` is used, which means:
- Each repository adds to existing data
- No data is cleared between extractions
- Use "Clear All" to reset completely

## API Changes

### New Endpoint Behavior

**GET `/api/v1/code/architecture`**
- **Before**: Served static JSON file
- **After**: Queries Neo4j for cumulative data
- **Returns**: Aggregated view of ALL repositories

**POST `/api/v1/code/extract-from-github`**
- **Parameter**: `append_mode` (default: `true`)
- **Behavior**: Appends to existing data in Neo4j
- **Set to `false`**: Clears before extraction (not recommended)

**POST `/api/v1/code/clear`**
- **Behavior**: Deletes ALL architecture data from Neo4j
- **Returns**: Count of deleted nodes

## Files Modified

1. **Backend**:
   - `sources/Api/app/endpoint/v1/routes/code_extraction.py`
   - `sources/Api/app/services/code_extraction/c4_extractor.py`

2. **Frontend**:
   - `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

3. **Documentation**:
   - `MULTI_REPO_IMPLEMENTATION.md` (this file)

## Known Limitations

1. **LLM Dependency**: Project name and description enrichment requires LLM
   - Fallback to heuristics if LLM unavailable
   - Ensure LM Studio is running on `http://127.0.0.1:1234`

2. **Owner Detection**: Requires git history in repository
   - Empty repositories will show "Unassigned"
   - ZIP uploads without .git won't have contributor data

3. **System Context Aggregation**: 
   - Currently creates one "Multi-Repository System" node
   - Could be enhanced to preserve individual system identities

## Future Enhancements

1. **Repository Tags**: Add tags/labels to group repositories by company/team
2. **System Separation**: Option to view individual systems separately
3. **Diff View**: Show what changed between repository additions
4. **Owner Override**: Allow manual owner specification
5. **Batch Import**: Add multiple repositories at once

## Support

For issues or questions:
1. Check logs: `make logs-api`
2. Verify Neo4j data: Navigate to Neo4j browser
3. Check LLM status: Ensure LM Studio is running
4. Review extraction status in UI

---

**Implementation Date**: January 28, 2026
**Status**: ✅ Complete and Tested
