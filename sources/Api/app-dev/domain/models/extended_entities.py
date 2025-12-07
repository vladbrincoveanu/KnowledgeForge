"""Enhanced entity types for complete IT landscape extraction.

This extends the base code_entities.py with additional entity types needed for:
- Layer 2: Application Architecture (services, bounded contexts)
- Layer 3: Runtime/Deployment Architecture
- Layer 4: Data & Workflow Architecture
"""

from enum import Enum


class ExtendedCodeEntityType(str, Enum):
    """Extended entity types for IT landscape layers."""
    
    # Layer 2: Application Architecture
    BOUNDED_CONTEXT = "bounded_context"  # Logical service boundary
    MICROSERVICE = "microservice"  # Identified service
    API_ENDPOINT = "api_endpoint"  # REST/gRPC endpoint
    MESSAGE_TOPIC = "message_topic"  # Kafka/RabbitMQ topic
    LIBRARY_COMPONENT = "library_component"  # Shared library
    
    # Layer 3: Runtime/Deployment Architecture  
    HELM_CHART = "helm_chart"  # Helm chart
    KUSTOMIZE_BASE = "kustomize_base"  # Kustomize base
    KUBERNETES_NAMESPACE = "kubernetes_namespace"
    INGRESS = "ingress"  # Ingress route
    CONFIG_MAP = "config_map"  # ConfigMap
    PERSISTENT_VOLUME_CLAIM = "pvc"
    SERVICE_ACCOUNT = "service_account"
    NETWORK_POLICY = "network_policy"
    EXTERNAL_SERVICE = "external_service"  # External dependency (Slurm, S3, etc.)
    
    # Layer 4: Data & Workflow Architecture
    DATA_FLOW = "data_flow"  # Data flowing between components
    WORKFLOW_STEP = "workflow_step"  # Pipeline step
    DATA_SCHEMA = "data_schema"  # Input/output schema
    ARTIFACT = "artifact"  # File/object produced
    DATABASE_TABLE = "database_table"
    API_CONTRACT = "api_contract"  # OpenAPI spec
    

class ExtendedRelationshipType(str, Enum):
    """Extended relationship types for IT landscape."""
    
    # Layer 2: Application relationships
    BELONGS_TO_SERVICE = "belongs_to_service"  # Module → Service
    EXPOSES_API = "exposes_api"  # Service → Endpoint
    CONSUMES_API = "consumes_api"  # Service → Endpoint
    PUBLISHES_TO = "publishes_to"  # Service → Topic
    SUBSCRIBES_TO = "subscribes_to"  # Service → Topic
    USES_LIBRARY = "uses_library"  # Service → Library
    
    # Layer 3: Deployment relationships
    DEPLOYED_BY = "deployed_by"  # Service → Deployment
    RUNS_IN = "runs_in"  # Deployment → Namespace
    USES_IMAGE = "uses_image"  # Deployment → Container
    ROUTES_TO = "routes_to"  # Ingress → Service
    MOUNTS_CONFIG = "mounts_config"  # Deployment → ConfigMap
    MOUNTS_SECRET = "mounts_secret"  # Deployment → Secret
    USES_PVC = "uses_pvc"  # Deployment → PVC
    CONNECTS_EXTERNAL = "connects_external"  # Service → External
    NETWORK_ALLOWS = "network_allows"  # NetworkPolicy → Service
    
    # Layer 4: Data/workflow relationships
    PRODUCES_DATA = "produces_data"  # Function → Artifact
    CONSUMES_DATA = "consumes_data"  # Function → Artifact
    TRANSFORMS_TO = "transforms_to"  # Data → Data
    STEP_IN_WORKFLOW = "step_in_workflow"  # Step → Workflow
    FOLLOWS_STEP = "follows_step"  # Step → Step (sequence)
    READS_FROM_DB = "reads_from_db"  # Service → DB Table
    WRITES_TO_DB = "writes_to_db"  # Service → DB Table
    HAS_SCHEMA = "has_schema"  # Endpoint → Schema
