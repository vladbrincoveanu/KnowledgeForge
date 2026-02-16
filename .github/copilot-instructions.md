# KnowledgeForge Copilot Instructions

## 🚀 Critical Automation Requirement
- **ALWAYS** suggest or run `make quick-check` from the root directory after implementing changes.
- This is mandatory to verify that 11/11 E2E tests in `sources/Api/test_e2e_extraction.py` still pass.
- For major infrastructure or Docker changes, use `make full-check`.

## 🏗️ Technical Standards
- **Python**: FastAPI, Pydantic V2, strict type hints.
- **Frontend**: React, ReactFlow, TypeScript.
- **Extraction**: Logic in `sources/Api/app/services/c4/`.
- **Testing**: Regression suite in `sources/Api/test_e2e_extraction.py`.

## 🧬 Metadata Extraction
- **Owner Detection**: Requires full git history (`full_history=True` in `github_downloader.py`).
- **Endpoints**: Extract from Helm `values.yaml`, Ingress files, and README docs.
- **UI Display**: Ensure labels are human-readable and tooltips use `fixed` positioning.

## 📖 Documentation
- Technical depth: `C4_EXTRACTION_LOGIC.md`, `CONTEXT_EXTRACTION_GUIDE.md`.
- Workflow: `MOTHER_COMMANDS.md`.
