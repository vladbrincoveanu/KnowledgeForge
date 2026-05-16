"""Canonical C4 container type taxonomy (from the C4 book, Chapter 4).

Containers are the applications and data stores that make up a software system.
Each container is a separately deployable/runnable unit.
"""

from enum import Enum


class C4ContainerType(str, Enum):
    """Book-canonical container types with their exact C4 labels."""

    # Application containers
    SERVER_SIDE_WEB_APP = "ServerSideWebApp"
    CLIENT_SIDE_WEB_APP = "ClientSideWebApp"
    MOBILE_APP = "MobileApp"
    CONSOLE_APP = "ConsoleApp"
    SERVERLESS_FUNCTION = "ServerlessFunction"
    SHELL_SCRIPT = "ShellScript"

    # Data store containers
    DATABASE = "Database"
    BLOB_STORE = "BlobStore"
    FILE_SYSTEM = "FileSystem"
    MESSAGE_BROKER = "MessageBroker"

    UNKNOWN = "Unknown"


def classify_c4_container_type(container: dict) -> C4ContainerType:
    """Map a detected container dict to a canonical C4ContainerType.

    Args:
        container: Dict with at least 'technology' and 'name' keys.
                   Optionally 'container_type' from the detector.

    Returns:
        The most specific C4ContainerType that matches.
    """
    tech = (container.get("technology") or "").lower()
    name = (container.get("name") or "").lower()
    ctype = (container.get("container_type") or "").lower()

    # Message broker — check first (Kafka is also sometimes called "database")
    if any(k in tech for k in ("kafka", "rabbitmq", "activemq", "nats", "sqs", "pubsub", "amqp")):
        return C4ContainerType.MESSAGE_BROKER
    if any(k in ctype for k in ("broker", "queue", "messaging", "event")):
        return C4ContainerType.MESSAGE_BROKER

    # Blob / object store
    if any(k in tech for k in ("s3", "minio", "blob", "gcs", "cloudfront", "cdn", "object store")):
        return C4ContainerType.BLOB_STORE
    if "blob" in ctype or "storage" in ctype:
        return C4ContainerType.BLOB_STORE

    # Database
    _db_techs = (
        "postgres", "postgresql", "mysql", "mariadb", "mongodb", "redis",
        "neo4j", "sqlite", "dynamodb", "cassandra", "elasticsearch",
        "opensearch", "oracle", "mssql", "sqlserver", "rds", "aurora",
        "cockroachdb", "tidb",
    )
    if any(k in tech for k in _db_techs):
        return C4ContainerType.DATABASE
    if any(k in ctype for k in ("database", "db", "store", "cache")):
        return C4ContainerType.DATABASE
    if any(k in name for k in ("db", "database", "store", "cache")):
        return C4ContainerType.DATABASE

    # Serverless function
    if any(k in tech for k in ("lambda", "azure function", "cloud function", "serverless")):
        return C4ContainerType.SERVERLESS_FUNCTION
    if "serverless" in ctype or "function" in ctype:
        return C4ContainerType.SERVERLESS_FUNCTION

    # Shell script
    if any(k in tech for k in ("bash", "shell", "sh", "zsh")):
        return C4ContainerType.SHELL_SCRIPT

    # Mobile app
    _mobile = ("ios", "android", "flutter", "react native", "swift", "kotlin", "xamarin", "ionic")
    if any(k in tech for k in _mobile):
        return C4ContainerType.MOBILE_APP
    if "mobile" in ctype:
        return C4ContainerType.MOBILE_APP

    # Client-side web app (SPA, frontend)
    _frontend_techs = ("react", "vue", "angular", "svelte", "next.js", "nuxt", "gatsby", "vite")
    if any(k in tech for k in _frontend_techs):
        if any(k in ctype for k in ("frontend", "spa", "web", "client", "ui")):
            return C4ContainerType.CLIENT_SIDE_WEB_APP
        if any(k in name for k in ("frontend", "spa", "ui", "web", "client")):
            return C4ContainerType.CLIENT_SIDE_WEB_APP

    # Server-side web application
    _server_techs = (
        "spring", "spring boot", "django", "flask", "fastapi", "rails",
        "express", "asp.net", "laravel", "symfony", "gin", "echo", "fiber",
        "node", "tomcat", "jetty", "quarkus", "micronaut",
    )
    if any(k in tech for k in _server_techs):
        return C4ContainerType.SERVER_SIDE_WEB_APP
    if any(k in ctype for k in ("api", "backend", "service", "server", "web")):
        return C4ContainerType.SERVER_SIDE_WEB_APP

    return C4ContainerType.UNKNOWN