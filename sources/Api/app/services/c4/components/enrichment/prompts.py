"""LLM prompt templates for element classification and component grouping.

Each template is a two-item tuple: (system_message, user_message_template).

Placeholders use .format() style:
  ELEMENT_CLASSIFICATION_PROMPT           — {elements_json}
  COMPONENT_GROUPING_PROMPT               — {elements_json}, {edges_json}
  COMPONENT_REFINEMENT_PROMPT             — {proposed_groups_json}, {elements_json}, {edges_json}
  SOURCE_COMPONENT_IDENTIFICATION_PROMPT  — {container_name}, {technology}, {file_tree},
                                            {source_files}, {already_detected_json}

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


# ---------------------------------------------------------------------------
# 4. Source-Based Component + Contract Identification
# ---------------------------------------------------------------------------

_SOURCE_COMPONENT_IDENTIFICATION_SYSTEM = """\
You are a senior software architect performing C4 Model Level 3 (Component) extraction.

A C4 component is a grouping of related functionality encapsulated behind
a well-defined interface (Simon Brown). Components are the building blocks
inside a deployable container.

Container: "{container_name}"
Technology: "{technology}"

---

COMPONENT TYPES (pick the single best fit):
  controller  — handles HTTP requests, routes, or user input entry points
  service     — encapsulates business logic and orchestrates operations
  repository  — abstracts data persistence (DB queries, ORM, DAOs)
  engine      — performs heavy computation, algorithms, or processing pipelines
  gateway     — integrates with external systems, APIs, or message brokers
  adapter     — translates between incompatible interfaces or protocols
  middleware  — cross-cutting interceptors (auth, logging, error handling)
  handler     — event/message handlers, webhook processors
  model       — data container, DTO, entity, or value object
  other       — does not fit any category above

ARCHITECTURAL LAYERS:
  presentation  — user-facing or API boundary
  business      — domain logic and use-case orchestration
  data_access   — persistence abstraction
  infrastructure — external integrations, config, messaging

---

CONTRACT TYPES (entry/exit points of this container):

1. HTTP/REST endpoints:
   - method + path (e.g., "GET /api/users/{{id}}")
   - request/response content types
   - auth requirements

2. GraphQL operations:
   - Query, Mutation, or Subscription
   - operation name and variables

3. gRPC services:
   - service name + method (e.g., "UserService.GetUser")
   - proto package

4. Message producers:
   - topic/queue name
   - message schema name (e.g., "OrderCreatedEvent")
   - what action publishes this

5. Message consumers:
   - topic/queue name
   - message schema name
   - handler method that processes it

6. Event emitters:
   - event name
   - payload schema (key fields)

7. WebSocket endpoints:
   - connection path
   - message formats

8. Webhook interfaces:
   - callback URLs
   - HTTP methods

9. CLI commands:
   - command name + arguments
   - description

---

Return ONLY raw JSON (no markdown, no explanation, no code fences) with this structure:
{{
  "components": [
    {{
      "name": "PaymentProcessor",
      "description": "Handles payment authorization and settlement via Stripe",
      "component_type": "service",
      "technology": "Python/stripe",
      "files": ["src/payments/processor.py", "src/payments/client.py"],
      "provided_interfaces": ["PaymentProcessor.charge()", "PaymentProcessor.refund()"],
      "required_interfaces": ["StripeAPI", "OrderRepository"],
      "architectural_layer": "business",
      "element_names": ["src.payments.processor.PaymentProcessor", "src.payments.client.StripeClient"]
    }}
  ],
  "contracts": [
    {{
      "contract_id": "payment-service-charge",
      "contract_type": "http_endpoint",
      "name": "POST /payments/charge",
      "direction": "provided",
      "component": "PaymentProcessor",
      "metadata": {{
        "method": "POST",
        "path": "/payments/charge",
        "content_type": "application/json",
        "auth": "JWT required"
      }},
      "description": "Charges a payment via Stripe"
    }}
  ]
}}
"""


_SOURCE_COMPONENT_IDENTIFICATION_USER = """\
Analyze this container and identify all components and contracts.

Container: "{container_name}"
Technology: "{technology}"

File structure:
{file_tree}

Source code:
{source_files}

Previously detected components (static analysis; empty list means none detected yet):
{already_detected_json}

Identify any ADDITIONAL components not already captured above (or ALL components if the list is empty).

For each component, provide:
  - name: human-readable architectural name
  - description: 1-2 sentences explaining responsibility
  - component_type: controller | service | repository | engine | gateway | adapter | middleware | handler | model | other
  - technology: specific framework/library used
  - files: source file paths belonging to this component
  - provided_interfaces: contracts this component EXPOSES
  - required_interfaces: contracts this component CONSUMES (other components, external services, databases)
  - architectural_layer: presentation | business | data_access | infrastructure
  - element_names: qualified names of parsed code elements in this component

For each contract, provide:
  - contract_id: unique identifier (e.g., "order-service-createorder")
  - contract_type: http_endpoint | graphql_operation | grpc_method | message_producer | message_consumer | event_emitter | websocket_endpoint | webhook | cli_command
  - name: display name (e.g., "POST /orders", "order.created topic")
  - direction: "provided" if exposed by this container, "required" if consumed from outside
  - component: which component provides/consumes this contract
  - metadata: type-specific fields (method, path, topic, schema, etc.)
  - description: one sentence

Respond ONLY with raw JSON (no markdown, no code fences).
"""

SOURCE_COMPONENT_IDENTIFICATION_PROMPT: tuple[str, str] = (
    _SOURCE_COMPONENT_IDENTIFICATION_SYSTEM,
    _SOURCE_COMPONENT_IDENTIFICATION_USER,
)
