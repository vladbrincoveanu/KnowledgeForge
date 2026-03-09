# Cursor Agent Prompts — C4 Component Extraction

## How to Use This File

**Before you start:**
1. Copy the `.cursorrules` content into `.cursor/rules/component-extraction.mdc` in your project
2. Run each prompt as a **separate Agent session** (Cmd+I) — don't chain them in one conversation
3. After each task, review the diff, commit, then start a new session for the next task
4. Use Claude Sonnet 4 or Gemini 2.5 Pro in Agent mode
5. Enable YOLO mode for test/build commands: `pytest, pip install, mkdir, touch`

**Prompt structure that works best:**
- Start with a single-line GOAL
- Give explicit file paths and constraints
- Reference existing code with @filename
- End with verification criteria
- Add "Don't modify any other files" when needed

---

## SPRINT 1: Foundation

### Task 1.1 — Data Models

```
Goal: Create all Pydantic data models for the C4 Component extraction pipeline.

Create the file `knowledgeforge/extractors/component/models.py` with these models:

1. `CodeElementKind` enum: CLASS, INTERFACE, ABSTRACT_CLASS, STRUCT, MODULE, FUNCTION, ENUM
2. `ArchitecturalLayer` enum: PRESENTATION, BUSINESS, DATA_ACCESS, INFRASTRUCTURE, UNKNOWN
3. `DependencyType` enum: IMPORT, CALL, INHERITANCE, INJECTION, SEMANTIC, DIRECTORY
4. `ExtractionMethod` enum: FRAMEWORK_DETECTION, COMMUNITY_DETECTION, HYBRID, MANUAL

5. `CodeElement` (Pydantic BaseModel):
   - name: str
   - qualified_name: str (e.g. "com.example.UserController")
   - kind: CodeElementKind
   - file_path: str
   - line_start: int
   - line_end: int
   - language: str
   - annotations: list[str] = []
   - decorators: list[str] = []
   - base_classes: list[str] = []
   - imports: list[str] = []
   - method_calls: list[str] = []
   - public_methods: list[str] = []
   - framework_role: str | None = None
   - layer: ArchitecturalLayer = ArchitecturalLayer.UNKNOWN

6. `DependencyEdge` (BaseModel):
   - source: str (qualified_name)
   - target: str (qualified_name)
   - dep_type: DependencyType
   - weight: float = 1.0

7. `ComponentRelationship` (BaseModel):
   - source_component: str
   - target_component: str
   - description: str
   - technology: str | None = None

8. `ComponentObject` (BaseModel):
   - name: str
   - description: str = ""
   - technology: str = ""
   - role: str = ""
   - layer: ArchitecturalLayer = ArchitecturalLayer.UNKNOWN
   - provided_interfaces: list[str] = []
   - required_interfaces: list[str] = []
   - relationships: list[ComponentRelationship] = []
   - code_elements: list[CodeElement] = []
   - file_paths: list[str] = []
   - parent_container_id: str = ""
   - confidence: float = 0.0
   - extraction_method: ExtractionMethod = ExtractionMethod.HYBRID

9. `FrameworkResult` (BaseModel):
   - framework_name: str
   - confidence: float
   - components: list[ComponentObject] = []
   - ungrouped: list[CodeElement] = []

Also create `knowledgeforge/extractors/component/__init__.py` that exports the key models.

Write tests in `tests/extractors/component/test_models.py` that verify:
- All enums have expected members
- CodeElement can be created with minimal fields
- ComponentObject serializes to/from JSON correctly
- DependencyEdge validates weight > 0

Don't modify any other files.
```

### Task 1.2 — Tree-sitter Parser

```
Goal: Implement the multi-language tree-sitter parser that walks a directory and parses source files into ASTs.

Create `knowledgeforge/extractors/component/parsing/__init__.py` and
`knowledgeforge/extractors/component/parsing/tree_sitter_parser.py`.

The TreeSitterParser class should:

1. Have a LANGUAGE_MAP dict mapping file extensions to tree-sitter language names:
   .py→python, .java→java, .ts→typescript, .tsx→tsx, .js→javascript,
   .go→go, .cs→c_sharp, .rs→rust, .kt→kotlin, .rb→ruby

2. Have a SKIP_DIRS set: {".git", "node_modules", "__pycache__", ".venv", "venv",
   "build", "dist", ".tox", ".mypy_cache", "target", ".gradle"}

3. Have a SKIP_PATTERNS list for test files: ["*_test.py", "test_*.py", "*Test.java",
   "*_test.go", "*.test.ts", "*.spec.ts", "__tests__/"]

4. Method `parse_file(file_path: str) -> ParsedFile | None`:
   - Detect language from extension
   - Use tree-sitter-language-pack's `get_parser(language)` to parse
   - Return a ParsedFile(file_path, language, tree) or None if unsupported

5. Method `parse_directory(root_path: str, skip_tests: bool = True) -> list[ParsedFile]`:
   - Walk directory recursively
   - Skip dirs in SKIP_DIRS
   - Optionally skip test files
   - Parse each supported file
   - Return list of ParsedFile objects

6. Create a ParsedFile model (simple dataclass or NamedTuple with file_path, language, tree fields)

Dependencies needed: `pip install tree-sitter tree-sitter-language-pack`

Write tests in `tests/extractors/component/parsing/test_tree_sitter_parser.py`:
- Create a temp directory with sample .py and .java files using pytest tmp_path fixture
- Verify parse_file returns correct language
- Verify parse_directory finds all files and skips node_modules
- Verify unsupported extensions return None
- Verify tree root node is not None for valid files

Don't modify any existing files outside of the component/ directory.
```

### Task 1.3 — Base Visitor

```
Goal: Create the abstract base visitor that all language-specific visitors will implement.

Create `knowledgeforge/extractors/component/parsing/visitors/__init__.py` and
`knowledgeforge/extractors/component/parsing/visitors/base_visitor.py`.

The BaseVisitor should be an ABC with:

1. Abstract method `visit(tree: Tree, file_path: str, source: bytes) -> list[CodeElement]`
   - Takes a tree-sitter Tree, the file path, and raw source bytes
   - Returns extracted CodeElement objects

2. Abstract property `supported_languages -> list[str]`
   - Returns which languages this visitor handles

3. Helper method `_node_text(node, source: bytes) -> str`
   - Extracts the text content of a tree-sitter node from source bytes

4. Helper method `_qualified_name(file_path: str, element_name: str) -> str`
   - Builds a qualified name from file path + element name
   - Python: convert path separators to dots, drop .py extension
   - Java: use package declaration if found, else path-based
   - Default: path-based dotted notation

5. Helper method `_detect_layer(annotations: list[str], name: str) -> ArchitecturalLayer`
   - Heuristic: if annotations contain controller/handler/route → PRESENTATION
   - If service/usecase/interactor → BUSINESS
   - If repository/dao/store/gateway → DATA_ACCESS
   - If config/middleware/interceptor → INFRASTRUCTURE
   - Else UNKNOWN

Use @models.py for the CodeElement and ArchitecturalLayer imports.

Write tests for the helper methods in `tests/extractors/component/parsing/visitors/test_base_visitor.py`.
Create a concrete stub visitor for testing the ABC contract.

Don't modify any other files.
```

### Task 1.4 — Python Visitor

```
Goal: Implement the Python language visitor that extracts classes, functions, and decorators from Python ASTs.

Create `knowledgeforge/extractors/component/parsing/visitors/python_visitor.py`.

The PythonVisitor(BaseVisitor) should extract CodeElements by traversing the tree-sitter AST:

1. Visit `class_definition` nodes:
   - Extract class name, decorators, base classes
   - Extract public methods (not starting with _)
   - Detect framework role from decorators:
     - @app.route / @router → "controller" (Flask/FastAPI)
     - Class inheriting APIView/ViewSet → "controller" (Django REST)
     - Class name ending in Service → "service"
     - Class name ending in Repository/Repo → "repository"
   - Set kind = CLASS (or ABSTRACT_CLASS if has ABC base or @abstractmethod)

2. Visit `function_definition` at module level (not inside a class):
   - Only include if decorated with routing decorators (@app.route, @router.get, etc.)
   - Or if the function name suggests architectural significance
   - Set kind = FUNCTION

3. Visit `import_statement` and `import_from_statement`:
   - Collect all imports and attach to the parent class/module

4. For each extracted element, detect the ArchitecturalLayer using the base helper.

Tree-sitter node types to use:
- `class_definition` → has `name`, `body`, `superclasses`, `decorator_list` children
- `function_definition` → has `name`, `parameters`, `body`, `decorator_list`
- `decorated_definition` → wraps a class/function with decorators
- `import_statement`, `import_from_statement` → import info
- `identifier` → name extraction

Use `node.children_by_field_name()` and `node.child_by_field_name()` for field access.

Write tests in `tests/extractors/component/parsing/visitors/test_python_visitor.py`:
- Fixture: a small Python source string with a Flask controller class, a service class, a repository class, and a standalone function
- Parse it with tree-sitter, visit it, verify:
  - Correct number of CodeElements extracted
  - Class names are correct
  - Decorators are captured
  - Base classes are captured
  - framework_role is detected for Flask routes
  - Imports are collected
- Edge case: empty file, file with only imports, syntax error file

Don't modify any other files.
```

### Task 1.5 — Sprint 1 Integration Test

```
Goal: Write an integration test that chains parser → visitor for a small Python project.

Create `tests/extractors/component/test_sprint1_integration.py`.

The test should:
1. Use pytest tmp_path to create a mini Python project structure:
   ```
   myapp/
   ├── __init__.py
   ├── controllers/
   │   └── user_controller.py  (Flask Blueprint with 2 route functions)
   ├── services/
   │   └── user_service.py     (UserService class with business methods)
   ├── repositories/
   │   └── user_repository.py  (UserRepository class)
   └── models/
       └── user.py             (User dataclass — should be filtered as non-architectural)
   ```

2. Use TreeSitterParser.parse_directory() to parse all files
3. Use PythonVisitor to visit each parsed file
4. Verify:
   - 3 architecturally significant elements found (controller, service, repository)
   - The User model class is extracted but has kind=CLASS (filtering happens later)
   - framework_role is correctly set: "controller", "service", "repository"
   - Imports between modules are captured

Also verify that `__pycache__` and `.git` directories would be skipped.

Run the tests with: pytest tests/extractors/component/ -v

Don't modify any other files.
```

---

## SPRINT 2: Multi-language Support

### Task 2.1 — Java Visitor

```
Goal: Implement the Java visitor that extracts classes, interfaces, and Spring/Jakarta annotations.

Create `knowledgeforge/extractors/component/parsing/visitors/java_visitor.py`.

The JavaVisitor(BaseVisitor) should handle:

1. `class_declaration` nodes:
   - Extract class name, modifiers (public/abstract)
   - Extract annotations: look for `annotation` or `marker_annotation` nodes
   - Map Spring annotations to roles:
     - @Controller, @RestController → "controller", layer=PRESENTATION
     - @Service → "service", layer=BUSINESS
     - @Repository → "repository", layer=DATA_ACCESS
     - @Component → role based on name heuristic
     - @Entity → skip (data model, not architectural)
     - @Configuration → "configuration", layer=INFRASTRUCTURE
   - Extract `implements` and `extends` (superclass, interfaces)
   - Extract public methods from `method_declaration` children

2. `interface_declaration` nodes:
   - Set kind=INTERFACE
   - Extract method signatures as provided_interfaces

3. `import_declaration` nodes:
   - Collect fully qualified imports
   - Use to resolve dependencies later

4. Package detection:
   - Find `package_declaration` at top of file
   - Use for qualified_name construction

Tree-sitter Java node types:
- `class_declaration` has fields: name, body, superclass, interfaces, modifiers
- `annotation` / `marker_annotation` → annotation names
- `method_declaration` → public methods
- `import_declaration` → imports
- `package_declaration` → package name

Write tests in `tests/extractors/component/parsing/visitors/test_java_visitor.py`:
- Fixture: Java source with @RestController class, @Service class, @Repository interface, @Entity class
- Verify correct role detection, annotation extraction, layer assignment
- Verify interface methods are captured as provided_interfaces
- Verify package name is used in qualified_name

Don't modify any other files.
```

### Task 2.2 — TypeScript Visitor

```
Goal: Implement the TypeScript/JavaScript visitor for NestJS and Express patterns.

Create `knowledgeforge/extractors/component/parsing/visitors/typescript_visitor.py`.

The TypeScriptVisitor(BaseVisitor) should handle both .ts and .js files:

1. `class_declaration` nodes:
   - Extract decorators (NestJS uses decorators like @Controller(), @Injectable())
   - Map NestJS decorators:
     - @Controller() → "controller", PRESENTATION
     - @Injectable() → check name: *Service→"service", *Repository→"repository", else "provider"
     - @Module() → skip (NestJS module config, not a component itself)
   - Extract constructor parameters (NestJS dependency injection)
   - Extract public methods

2. `export_statement` with function or const (Express/Fastify style):
   - Detect Router instances: `express.Router()`, `new Router()`
   - Detect exported handler functions with req/res params → "controller"

3. `import_statement` nodes:
   - Handle both `import { X } from 'y'` and `import X from 'y'` and `require('y')`

4. Support both TypeScript and TSX (React components → PRESENTATION layer)

Tree-sitter TypeScript node types:
- `class_declaration`, `abstract_class_declaration`
- `decorator` → for NestJS
- `export_statement` → wraps exported declarations
- `import_statement` → imports
- `function_declaration`, `arrow_function`, `variable_declarator`

Write tests with NestJS-style and Express-style fixture code.

Don't modify any other files.
```

### Task 2.3 — Go Visitor

```
Goal: Implement the Go visitor for struct, interface, and handler detection.

Create `knowledgeforge/extractors/component/parsing/visitors/go_visitor.py`.

Go has no annotations/decorators, so detection relies on:

1. `type_declaration` → struct types:
   - Extract struct name and fields
   - If struct has methods with (w http.ResponseWriter, r *http.Request) params → "handler"
   - If struct name ends in Service/Svc → "service"
   - If struct name ends in Repository/Repo/Store → "repository"
   - If struct implements an interface (check method sets) → note the interface

2. `type_declaration` → interface types:
   - Extract interface name and method signatures
   - Set kind=INTERFACE

3. `function_declaration` at package level:
   - If has http handler signature → "controller"
   - If registered as route handler (heuristic: name starts with Handle/Get/Post/Put/Delete)

4. `package_clause` → package name for qualified naming

5. `import_declaration` → imports (Go uses path-based imports)

Go is organized by package, so the qualified_name should be: module_path/package.TypeName

Write tests with a Go HTTP handler struct, a service struct, and a repository interface.

Don't modify any other files.
```

---

## SPRINT 3: Dependency Graph

### Task 3.1 — Structural Dependencies

```
Goal: Implement structural dependency extraction (imports, calls, inheritance, injection).

Create `knowledgeforge/extractors/component/graph/structural_deps.py`.

The StructuralDependencyAnalyzer class:

1. Method `analyze(elements: list[CodeElement]) -> list[DependencyEdge]`:
   - Build a lookup: qualified_name → CodeElement, name → CodeElement
   - For each element, resolve its `imports` list to other elements:
     - Match by qualified_name (exact)
     - Match by simple name (fallback)
     - Create IMPORT edge with weight=1.0
   - For each element, resolve `base_classes` to other elements:
     - Create INHERITANCE edge with weight=2.0
   - For each element, resolve `method_calls` to target elements:
     - Create CALL edge with weight=1.5
   - Detect injection patterns (constructor params matching other element types):
     - Create INJECTION edge with weight=2.0

2. Import resolution should handle:
   - Python: `from myapp.services.user_service import UserService`
   - Java: `import com.example.service.UserService`
   - TypeScript: `import { UserService } from '../services/user.service'`
   - Go: `import "myapp/services"`
   - Resolve relative paths to qualified names

3. Deduplication: if same source→target has multiple edge types, keep all but don't duplicate same type.

Write tests using the CodeElement fixtures from Sprint 1 — create a set of 4-5 elements with known imports and verify the correct edges are produced.

Don't modify any other files.
```

### Task 3.2 — Directory Dependencies

```
Goal: Implement directory-based dependency weighting.

Create `knowledgeforge/extractors/component/graph/directory_deps.py`.

The DirectoryDependencyAnalyzer:

1. Method `analyze(elements: list[CodeElement]) -> list[DependencyEdge]`:
   - For each pair of elements, compute directory proximity
   - Same directory → weight 0.3, type=DIRECTORY
   - Parent/child directory → weight 0.15
   - Sibling directories (same parent) → weight 0.1
   - More than 2 levels apart → no edge
   - Only create directory edges between elements NOT already connected structurally

2. Method `_directory_distance(path_a: str, path_b: str) -> int`:
   - Returns the number of directory levels between two file paths
   - Same dir = 0, parent/child = 1, siblings = 2, etc.

Takes the list of existing structural edges as an optional parameter to avoid duplicating already-connected pairs.

Write tests: create elements in same dir, adjacent dirs, and distant dirs. Verify correct weights.

Don't modify any other files.
```

### Task 3.3 — Dependency Graph Builder

```
Goal: Build the combined weighted NetworkX dependency graph.

Create `knowledgeforge/extractors/component/graph/__init__.py` and
`knowledgeforge/extractors/component/graph/dependency_graph.py`.

The DependencyGraphBuilder class:

1. Method `build(elements, structural_edges, directory_edges, semantic_edges=None) -> nx.DiGraph`:
   - Create a NetworkX DiGraph
   - Add one node per CodeElement (node id = qualified_name, store element as node data)
   - Add all edges from all sources
   - If same source→target pair appears multiple times, SUM their weights
   - Store edge metadata: dep_types list, combined_weight

2. Method `get_undirected_weighted(graph: nx.DiGraph) -> nx.Graph`:
   - Convert to undirected for clustering algorithms
   - For bidirectional edges, sum weights in both directions

3. Method `get_subgraph(graph: nx.DiGraph, elements: list[CodeElement]) -> nx.DiGraph`:
   - Return induced subgraph for a subset of elements

4. Method `summary(graph: nx.DiGraph) -> dict`:
   - Return node count, edge count, density, connected components count

Write tests: build a graph from known elements/edges, verify node count, edge weights, conversion to undirected.

Don't modify any other files.
```

---

## SPRINT 4: Component Grouping

### Task 4.1 — Spring Framework Detector

```
Goal: Implement the Spring framework pattern detector as the first and most important framework matcher.

Create `knowledgeforge/extractors/component/grouping/framework_detector.py`.

Start with the base interface and Spring implementation:

1. Abstract `FrameworkMatcher`:
   - `detect(elements: list[CodeElement]) -> float` — returns confidence 0.0-1.0
   - `group(elements: list[CodeElement]) -> FrameworkResult` — groups into components

2. `SpringPatternMatcher(FrameworkMatcher)`:
   - detect(): check if >30% of elements have Spring annotations → high confidence
   - group():
     a. Separate elements by Spring role: controllers, services, repositories, components, other
     b. Group by domain prefix: extract the domain noun from class names
        - UserController + UserService + UserRepository → "User" domain
        - OrderController + OrderService → "Order" domain
        - Use longest common prefix/suffix stripping (remove Controller/Service/Repository/Impl suffixes)
     c. For each domain group, create a ComponentObject:
        - name = "{Domain} Component" (e.g., "User Management")
        - technology = "Spring"
        - layer = determined by highest-layer element in group
        - code_elements = all elements in this domain group
     d. Elements that don't match any domain group → return as ungrouped

3. `FrameworkDetectorRegistry`:
   - Holds all matchers, tries each one
   - Returns the result from the highest-confidence matcher above threshold (0.5)

Write tests with mock Spring-annotated CodeElements. Verify domain grouping produces expected components.

Don't modify any other files.
```

### Task 4.2 — Django + FastAPI Matchers

```
Goal: Add Django and FastAPI framework pattern matchers to the framework detector.

Add to `knowledgeforge/extractors/component/grouping/framework_detector.py`:

1. `DjangoPatternMatcher(FrameworkMatcher)`:
   - detect(): check for Django patterns — files named models.py, views.py, serializers.py, admin.py, urls.py
   - group():
     - Group by Django app (each directory with models.py = one app)
     - Within each app, all elements form one component
     - name = directory name (e.g., "accounts", "orders")
     - If app has views.py → layer=PRESENTATION
     - If app has only models.py → layer=DATA_ACCESS

2. `FastAPIPatternMatcher(FrameworkMatcher)`:
   - detect(): check for FastAPI patterns — `@router` decorators, APIRouter imports
   - group():
     - Group by router file (each router file = one component)
     - Or by directory if using directory-based organization
     - Detect Depends() injection for dependency mapping

Register both in FrameworkDetectorRegistry.

Write tests for each matcher with appropriate fixture elements.

Don't modify any other files.
```

### Task 4.3 — Community Detection (Louvain Clustering)

```
Goal: Implement the fallback community detection for containers without recognized frameworks.

Create `knowledgeforge/extractors/component/grouping/community_detector.py`.

Dependencies: `pip install python-louvain`

The CommunityDetector class:

1. Method `detect(graph: nx.Graph, min_size: int = 2, resolution: float = 1.0) -> dict[str, int]`:
   - Apply Louvain community detection (community.best_partition)
   - Input: undirected weighted graph from DependencyGraphBuilder
   - Returns: mapping of node_id → cluster_id

2. Method `post_process(partition: dict, graph: nx.Graph, min_size: int, max_size: int = 15) -> dict`:
   - Merge singletons: assign isolated nodes to nearest neighbor's cluster
   - Split large clusters: if cluster > max_size, re-run Louvain on subgraph with higher resolution
   - Remove empty clusters and re-number

3. Method `partition_to_groups(partition: dict, elements: list[CodeElement]) -> list[list[CodeElement]]`:
   - Convert cluster partition to lists of CodeElements grouped by cluster

4. Method `name_cluster(elements: list[CodeElement]) -> str`:
   - Heuristic naming: find most common name tokens across elements
   - Or use the directory name they share
   - Fallback: "Component {N}"

Write tests:
- Create a graph with two obvious clusters (dense internal, sparse cross-cluster edges)
- Verify Louvain separates them correctly
- Test singleton merging
- Test large cluster splitting

Don't modify any other files.
```

### Task 4.4 — Grouping Strategy Orchestrator

```
Goal: Implement the two-tier grouping strategy that tries framework detection first, then falls back to clustering.

Create `knowledgeforge/extractors/component/grouping/grouping_strategy.py` and
`knowledgeforge/extractors/component/grouping/component_builder.py`.

1. GroupingStrategy class:
   - Method `group(elements: list[CodeElement], dep_graph: nx.DiGraph) -> list[ComponentObject]`:
     a. Run FrameworkDetectorRegistry.detect_and_group(elements)
     b. If confidence > 0.5: take framework components + collect ungrouped remainder
     c. If confidence <= 0.5: all elements are "remainder"
     d. For remainder: build subgraph → convert to undirected → run CommunityDetector
     e. Combine framework components + clustered components
     f. For each component, build ComponentObject via ComponentBuilder

2. ComponentBuilder class:
   - Method `build(group: list[CodeElement], extraction_method: ExtractionMethod) -> ComponentObject`:
     - name: from framework name or cluster naming heuristic
     - technology: inferred from language + framework of elements
     - role: most common framework_role in group, or heuristic from element kinds
     - layer: highest-significance layer in group
     - code_elements: the group
     - file_paths: unique file paths from elements
     - provided_interfaces: union of all public_methods across elements
     - required_interfaces: union of all imports pointing outside this component
     - confidence: framework=0.9, community=0.6, singleton=0.3

Write integration test: create elements mimicking a Spring app with some non-Spring utility classes.
Verify Spring elements get framework-detected, utilities get clustered.

Don't modify any other files.
```

---

## SPRINT 5: LLM Enrichment + Main Orchestrator

### Task 5.1 — LLM Enrichment Prompts and Service

```
Goal: Implement the LLM enrichment layer that generates human-readable component names and descriptions.

Create `knowledgeforge/extractors/component/enrichment/prompts.py` and
`knowledgeforge/extractors/component/enrichment/llm_enricher.py`.

1. prompts.py:
   - COMPONENT_NAMING_PROMPT template that takes:
     - container_name, container_technology
     - list of code element names, roles, file paths
     - Returns JSON with: name, description, responsibility, layer
   - INTERFACE_EXTRACTION_PROMPT template for provided/required interface refinement

2. ComponentLLMEnricher class:
   - Uses the existing LLM service from the project (check @knowledgeforge/llm/ for the interface)
   - Method `enrich(component: ComponentObject, container_info: dict) -> ComponentObject`:
     - Build context from component's code_elements
     - Call LLM with COMPONENT_NAMING_PROMPT
     - Parse JSON response, update component fields
     - If LLM unavailable or fails, keep the static-analysis name as fallback
   - Method `enrich_batch(components: list[ComponentObject], container_info: dict) -> list[ComponentObject]`:
     - Enrich all components, with error handling per component
     - Use async if LLM service supports it

Make the LLM call optional — the enricher should gracefully degrade if no LLM is configured.

Write tests with a mock LLM service that returns fixed JSON. Verify enrichment updates fields correctly. Verify fallback when LLM fails.

Don't modify any other files.
```

### Task 5.2 — Main Orchestrator

```
Goal: Implement the ComponentExtractor that orchestrates the full A→B→C→D pipeline.

Create `knowledgeforge/extractors/component/component_extractor.py`.

The ComponentExtractor class:

1. Constructor takes:
   - llm_service: optional LLM service instance (None = skip enrichment)
   - config: optional dict for resolution, min_component_size, skip_tests, etc.

2. Method `extract(container_root_path: str, container_info: dict = None) -> list[ComponentObject]`:

   Phase A — Parse:
   - Use TreeSitterParser.parse_directory(container_root_path)
   - For each parsed file, select the appropriate visitor by language
   - Collect all CodeElements via ElementRegistry (dedup by qualified_name)

   Phase B — Graph:
   - Run StructuralDependencyAnalyzer
   - Run DirectoryDependencyAnalyzer
   - Build DependencyGraphBuilder.build()

   Phase C — Group:
   - Run GroupingStrategy.group(elements, graph)

   Phase D — Enrich (if LLM available):
   - Run ComponentLLMEnricher.enrich_batch(components, container_info)

   Return: list of ComponentObjects

3. Method `extract_for_container(container: ContainerObject) -> ContainerObject`:
   - Calls extract() with container's root path
   - Attaches results to container.components
   - Returns updated container

Add logging at each phase transition: "Phase A: parsed {n} files, extracted {m} elements"

Write an integration test that runs the full pipeline on the Sprint 1 mini Python project fixture.
Verify the output contains expected ComponentObjects with correct names and relationships.

Don't modify any other files outside component/.
```

---

## SPRINT 6: Polish

### Task 6.1 — Element Registry and Deduplication

```
Goal: Implement the ElementRegistry that collects, deduplicates, and filters CodeElements across all visitors.

Create `knowledgeforge/extractors/component/parsing/element_registry.py`.

The ElementRegistry:
1. Collects elements from multiple visitors
2. Deduplicates by qualified_name (keep the one with more metadata)
3. Filters non-architectural elements:
   - Data classes: >70% of body is field declarations, <3 methods
   - Utility classes: all static methods, no state
   - Generated code: filename matches *_pb2.py, *.generated.*, etc.
4. Returns the filtered, deduplicated list

Mark filtered elements with a flag (don't discard — they're useful as metadata).

Write tests for dedup and each filter rule.

Don't modify any other files.
```

### Task 6.2 — Semantic Dependencies (TF-IDF)

```
Goal: Add semantic similarity-based dependency edges using TF-IDF on element identifiers.

Create `knowledgeforge/extractors/component/graph/semantic_deps.py`.

The SemanticDependencyAnalyzer:

1. For each CodeElement, extract tokens:
   - Split camelCase and snake_case names into words
   - Include class name, method names, variable names from the element
   - Lowercase all tokens

2. Compute TF-IDF vectors using sklearn's TfidfVectorizer

3. Compute pairwise cosine similarity

4. Create SEMANTIC edges where similarity > threshold (default 0.5)
   - Weight = similarity_score * 0.5 (lower than structural)

5. Only create edges between elements NOT already structurally connected

Dependencies: scikit-learn (should already be installed)

Write tests with elements that have similar names (UserService, UserRepository) vs unrelated names (EmailSender, DatabaseMigrator).

Don't modify any other files.
```

---

## Tips for Each Session

1. **Start each session by referencing the plan**: "@c4-component-extraction-plan.md implementing Task X.Y"
2. **Pin relevant existing files**: "@models.py @base_visitor.py" so the agent sees the interfaces to implement against
3. **After each task completes**, run: `pytest tests/extractors/component/ -v --tb=short` and paste failures back
4. **If the agent struggles**, break the task in half — e.g., "Just implement the class skeleton with method signatures and docstrings, no logic yet"
5. **If it modifies unrelated files**, add: "ONLY create/modify files under knowledgeforge/extractors/component/ and tests/extractors/component/"
6. **Commit after each green test run** — this gives you rollback points
