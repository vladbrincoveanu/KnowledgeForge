# KnowledgeForge - C4 Component Extraction Rules

## Project Context
This is a Python project called KnowledgeForge that extracts C4 architecture models from source code repositories. We are implementing the **Component-level** extraction layer that sits between the existing Container Extractor and System Context Builder. The component extraction code lives under `sources/Api/app/services/c4/components/`.

## Tech Stack
- Python 3.11+
- tree-sitter + tree-sitter-language-pack for AST parsing
- NetworkX for dependency graphs
- python-louvain for community detection
- Pydantic v2 for data models
- pytest for testing

## Code Style
- Use type hints everywhere, including return types
- Use Pydantic BaseModel for all data models, not dataclasses
- Use async/await for LLM calls only; keep parsing synchronous
- Use Enum classes for all string constants (roles, layers, kinds)
- Follow existing project patterns in `sources/Api/app/services/c4/containers/` and `sources/Api/app/services/c4/context/`
- Docstrings: Google style, one-line summary + Args/Returns sections
- Max line length: 100 characters
- Imports: stdlib → third-party → local, separated by blank lines

## Architecture Rules
- Each module should have a single responsibility
- Visitors must inherit from `BaseVisitor` and implement `visit(tree, file_path) -> List[CodeElement]`
- All dependency analyzers must implement `analyze(elements) -> List[DependencyEdge]`
- Framework detectors must implement `detect_and_group(elements) -> FrameworkResult`
- Never mutate input data; always return new objects
- Use the Strategy pattern for grouping (framework detection → clustering fallback)

## Testing Rules
- Write tests BEFORE implementation when asked to implement a module
- Use pytest with fixtures, not unittest
- Place tests in `sources/Api/tests/services/c4/components/` mirroring source structure
- Use real small code snippets as fixtures (not mocks) for tree-sitter parsing tests
- Test edge cases: empty files, files with syntax errors, mixed languages
- Every public method needs at least one test

## File Structure
```
sources/Api/app/services/c4/components/
├── __init__.py
├── component_extractor.py
├── models.py
├── parsing/
│   ├── __init__.py
│   ├── tree_sitter_parser.py
│   ├── visitors/
│   │   ├── __init__.py
│   │   ├── base_visitor.py
│   │   ├── python_visitor.py
│   │   ├── java_visitor.py
│   │   ├── typescript_visitor.py
│   │   └── go_visitor.py
│   └── element_registry.py
├── graph/
│   ├── __init__.py
│   ├── dependency_graph.py
│   ├── structural_deps.py
│   ├── semantic_deps.py
│   └── directory_deps.py
├── grouping/
│   ├── __init__.py
│   ├── framework_detector.py
│   ├── community_detector.py
│   ├── grouping_strategy.py
│   └── component_builder.py
└── enrichment/
    ├── __init__.py
    ├── llm_enricher.py
    ├── prompts.py
    └── interface_extractor.py
```

## Test Structure
```
sources/Api/tests/services/c4/components/
├── __init__.py
├── test_models.py
├── test_component_extractor.py
├── parsing/
│   ├── __init__.py
│   ├── test_tree_sitter_parser.py
│   └── visitors/
│       ├── __init__.py
│       ├── test_base_visitor.py
│       ├── test_python_visitor.py
│       ├── test_java_visitor.py
│       └── test_typescript_visitor.py
├── graph/
│   ├── __init__.py
│   ├── test_dependency_graph.py
│   ├── test_structural_deps.py
│   └── test_directory_deps.py
└── grouping/
    ├── __init__.py
    ├── test_framework_detector.py
    ├── test_community_detector.py
    └── test_grouping_strategy.py
```

## Key Domain Terms
- **CodeElement**: A single class, interface, function, or module extracted from source code
- **ComponentObject**: A C4 Component = a group of related CodeElements within a Container
- **DependencyEdge**: A weighted, typed edge between two CodeElements
- **ContainerObject**: The parent C4 Container (already exists in codebase)
- **Framework pattern**: Known code organization conventions (Spring @Service, Django apps, NestJS modules)

## Don'ts
- Don't use language-specific AST libraries (like Python's `ast` module) — use tree-sitter for everything
- Don't write regex-based parsers as the primary extraction method
- Don't add dependencies without checking if tree-sitter-language-pack already covers it
- Don't put business logic in models.py — keep it in the appropriate phase module
- Don't create God classes — the ComponentExtractor orchestrator should delegate, not implement
- Don't modify files outside of `sources/Api/app/services/c4/components/` and `sources/Api/tests/services/c4/components/` unless explicitly asked