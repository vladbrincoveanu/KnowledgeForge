"""LLM prompt templates for element classification and component grouping.

Each template is a two-item tuple: (system_message, user_message_template).

Placeholders use .format() style:
  ELEMENT_CLASSIFICATION_PROMPT  — {elements_json}
  COMPONENT_GROUPING_PROMPT      — {elements_json}, {edges_json}
  COMPONENT_REFINEMENT_PROMPT    — {proposed_groups_json}, {elements_json}, {edges_json}

All templates instruct the LLM to respond with raw JSON only (no markdown fences).
"""

# ---------------------------------------------------------------------------
# 1. Element Classification
# ---------------------------------------------------------------------------

_ELEMENT_CLASSIFICATION_SYSTEM = """\
You are a senior software architect analyzing source code structure.
Your task is to classify individual code elements by their architectural role and layer.

Architectural roles (pick the single best fit):
  controller  — handles HTTP requests, routes, or user input entry points
  service     — encapsulates business logic and orchestrates operations
  repository  — abstracts data persistence (DB queries, ORM, DAOs)
  engine      — performs heavy computation, algorithms, or processing pipelines
  gateway     — integrates with external systems, APIs, or message brokers
  adapter     — translates between incompatible interfaces or protocols
  util        — stateless helper functions or pure utilities with no domain logic
  model       — data container, DTO, entity, or value object with no behavior
  config      — configuration loading, environment parsing, or wiring
  middleware  — cross-cutting interceptors (auth, logging, error handling)
  other       — does not fit any category above

Architectural layers:
  presentation  — user-facing or API boundary (controllers, serializers, views)
  business      — domain logic and use-case orchestration (services, engines)
  data_access   — persistence abstraction (repositories, DAOs, migrations)
  infrastructure — external integrations, config, messaging, cross-cutting concerns
  unknown       — cannot be determined from the available information

Significance: an element is architecturally significant if it encodes domain logic,
defines a contract (interface/abstract class), or acts as a primary entry/exit point.
Data models, DTOs, pure helpers, and config classes are generally NOT significant.

Respond ONLY with a JSON array. No markdown, no explanation, no code fences.\
"""

_ELEMENT_CLASSIFICATION_USER = """\
Classify each of the following code elements.

Elements (JSON array):
{elements_json}

Each element object has:
  qualified_name   — fully-qualified class/function name
  kind             — class | interface | abstract_class | struct | module | function | enum
  file_path        — source file path
  language         — programming language
  annotations      — list of decorators or annotations (e.g. @Controller, @pytest.mark.*)
  imports          — list of imported module/package names
  base_classes     — list of parent class names
  method_calls     — list of external method or function calls made by this element

Return a JSON array where each object has exactly these fields:
  element_name   — the qualified_name of the element (string)
  role           — one of: controller, service, repository, engine, gateway, adapter,
                   util, model, config, middleware, other
  layer          — one of: presentation, business, data_access, infrastructure, unknown
  is_significant — true or false
  reasoning      — one sentence explaining the classification (string)

Respond with the JSON array only. No markdown, no code fences.\
"""

ELEMENT_CLASSIFICATION_PROMPT: tuple[str, str] = (
    _ELEMENT_CLASSIFICATION_SYSTEM,
    _ELEMENT_CLASSIFICATION_USER,
)


# ---------------------------------------------------------------------------
# 2. Component Grouping
# ---------------------------------------------------------------------------

_COMPONENT_GROUPING_SYSTEM = """\
You are a senior software architect applying C4 model principles to group code elements
into components.

A C4 component is a grouping of related code that:
  - Has a single, clearly bounded responsibility
  - Has high internal cohesion (elements collaborate closely)
  - Has low external coupling (minimal, intentional dependencies on other components)
  - Would be deployed or versioned together
  - Can be described in one sentence

Component types (pick the single best fit):
  controller    — handles HTTP requests, routes, or user input entry points
  service       — encapsulates business logic and orchestrates operations
  repository    — abstracts data persistence (DB queries, ORM, DAOs)
  handler       — processes events, messages, or commands
  gateway       — integrates with external systems, APIs, or message brokers
  engine        — performs heavy computation, algorithms, or processing pipelines
  middleware    — cross-cutting interceptors (auth, logging, error handling)
  configuration — configuration loading, environment parsing, or wiring
  component     — general-purpose component that does not fit a more specific type

Component roles mirror element roles but at a coarser grain:
  controller, service, repository, engine, gateway, adapter, util, config, other

Architectural layers are the same as for elements:
  presentation, business, data_access, infrastructure, unknown

For interfaces:
  provided_interfaces — contracts this component exposes to callers
  required_interfaces — contracts this component depends on from others

Respond ONLY with a JSON array. No markdown, no explanation, no code fences.\
"""

_COMPONENT_GROUPING_USER = """\
Group the following classified code elements into C4 components.

Classified elements (JSON array):
{elements_json}

Dependency edges (JSON array of {{source, target, dependency_type, weight}}):
{edges_json}

Guidelines:
  - Every element must appear in exactly one component.
  - Prefer grouping by bounded responsibility over grouping by layer.
  - A component may contain elements from different layers if they form a cohesive unit
    (e.g., a service class together with its domain model).
  - Singletons are acceptable only when the element is genuinely self-contained.
  - Name components using domain vocabulary, not technical suffixes
    (prefer "OrderManagement" over "OrderServiceGroup").

Return a JSON array where each object has exactly these fields:
  name                — short, domain-meaningful component name (string)
  description         — one sentence describing what this component does (string)
  component_type      — one of: controller, service, repository, handler, gateway,
                        engine, middleware, configuration, component
  role                — one of: controller, service, repository, engine, gateway,
                        adapter, util, config, other
  layer               — one of: presentation, business, data_access, infrastructure, unknown
  element_names       — list of qualified_name strings belonging to this component
  provided_interfaces — list of interface/abstract class qualified_names this component exposes
  required_interfaces — list of interface/abstract class qualified_names this component consumes

Respond with the JSON array only. No markdown, no code fences.\
"""

COMPONENT_GROUPING_PROMPT: tuple[str, str] = (
    _COMPONENT_GROUPING_SYSTEM,
    _COMPONENT_GROUPING_USER,
)


# ---------------------------------------------------------------------------
# 3. Component Refinement
# ---------------------------------------------------------------------------

_COMPONENT_REFINEMENT_SYSTEM = """\
You are a senior software architect reviewing an algorithmically proposed component grouping.

The grouping was produced by Louvain community detection, which optimises for graph
modularity but has no awareness of domain semantics or C4 principles. Your job is to
correct its mistakes:

  Merge   — two groups that share the same bounded responsibility should become one component.
  Split   — a group that mixes unrelated responsibilities should be divided.
  Rename  — a group whose name is generic or misleading should get a clearer domain name.
  Keep    — a group that is already cohesive and well-named should be left as-is.

Apply the same C4 component criteria as always:
  single bounded responsibility, high internal cohesion, low external coupling.

Component types (pick the single best fit for each component):
  controller    — handles HTTP requests, routes, or user input entry points
  service       — encapsulates business logic and orchestrates operations
  repository    — abstracts data persistence (DB queries, ORM, DAOs)
  handler       — processes events, messages, or commands
  gateway       — integrates with external systems, APIs, or message brokers
  engine        — performs heavy computation, algorithms, or processing pipelines
  middleware    — cross-cutting interceptors (auth, logging, error handling)
  configuration — configuration loading, environment parsing, or wiring
  component     — general-purpose component that does not fit a more specific type

Respond ONLY with a JSON array. No markdown, no explanation, no code fences.\
"""

_COMPONENT_REFINEMENT_USER = """\
Review and refine the following Louvain-proposed component grouping.

Proposed groups (JSON array — same schema as the output format below):
{proposed_groups_json}

Code elements with classification metadata (JSON array):
{elements_json}

Dependency edges (JSON array of {{source, target, dependency_type, weight}}):
{edges_json}

For each proposed group, decide whether to keep, merge, split, or rename it.
Every element must appear in exactly one component in your output.

Return a JSON array where each object has exactly these fields:
  name                — short, domain-meaningful component name (string)
  description         — one sentence describing what this component does (string)
  component_type      — one of: controller, service, repository, handler, gateway,
                        engine, middleware, configuration, component
  role                — one of: controller, service, repository, engine, gateway,
                        adapter, util, config, other
  layer               — one of: presentation, business, data_access, infrastructure, unknown
  element_names       — list of qualified_name strings belonging to this component
  provided_interfaces — list of interface/abstract class qualified_names this component exposes
  required_interfaces — list of interface/abstract class qualified_names this component consumes

Respond with the JSON array only. No markdown, no code fences.\
"""

COMPONENT_REFINEMENT_PROMPT: tuple[str, str] = (
    _COMPONENT_REFINEMENT_SYSTEM,
    _COMPONENT_REFINEMENT_USER,
)
