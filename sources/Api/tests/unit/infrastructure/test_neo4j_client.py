import pytest
from unittest.mock import MagicMock, patch


class TestNeo4jClientInit:
    def test_from_config_creates_client_with_defaults(self):
        with patch("app.infrastructure.graph.neo4j_client.get_config") as mock_config, \
             patch("app.infrastructure.graph.neo4j_client.GraphDatabase") as mock_gdb:
            mock_config.return_value.neo4j = MagicMock(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="password123",
                database="neo4j",
                encrypted=False,
                max_connection_pool_size=50,
                connection_timeout=30,
            )
            mock_driver = MagicMock()
            mock_gdb.driver.return_value = mock_driver
            mock_driver.verify_connectivity.return_value = None

            from app.infrastructure.graph.neo4j_client import Neo4jClient
            client = Neo4jClient.from_config()
            assert client.uri == "bolt://localhost:7687"
            assert client.database == "neo4j"


class TestNeo4jClientUpsertNode:
    def test_upsert_node_uses_merge_cypher(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.upsert_node("Container", "container:airbyte-api", {"name": "airbyte-api", "level": "container"})

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        kwargs = mock_session.run.call_args[1]
        assert "MERGE" in cypher
        assert "(n:`Container` {id: $node_id})" in cypher
        assert kwargs["node_id"] == "container:airbyte-api"
        assert kwargs["props"] == {"name": "airbyte-api", "level": "container"}


class TestNeo4jClientUpsertRelationship:
    def test_upsert_relationship_creates_merge_pattern(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.upsert_relationship(
            "USES",
            "container:openapi2jsonschema->container:docker",
            "container:openapi2jsonschema",
            "container:docker",
            {"protocol": "HTTP", "description": "uses docker"},
        )

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        kwargs = mock_session.run.call_args[1]
        assert "MERGE" in cypher
        assert "`USES`" in cypher
        assert kwargs["rel_id"] == "container:openapi2jsonschema->container:docker"
        assert kwargs["from_id"] == "container:openapi2jsonschema"
        assert kwargs["to_id"] == "container:docker"
        assert kwargs["props"] == {"protocol": "HTTP", "description": "uses docker"}


class TestNeo4jClientClearExtraction:
    def test_clear_extraction_deletes_by_task_id(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.clear_extraction("task-abc-123")

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        kwargs = mock_session.run.call_args[1]
        assert "extraction_task_id" in cypher
        assert kwargs["task_id"] == "task-abc-123"


class TestNeo4jClientQuery:
    def test_query_returns_list_of_dicts(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_record = MagicMock()
        mock_record.keys.return_value = ["count"]
        mock_record.__getitem__ = lambda self, k: 5
        mock_record.__iter__ = lambda self: iter(["count"])
        mock_session.run.return_value = [mock_record]

        result = client.query("MATCH (n:Container) RETURN count(n) as count", {"limit": 10})
        assert len(result) == 1
        assert result[0] == {"count": 5}
        args, kwargs = mock_session.run.call_args
        assert args[0] == "MATCH (n:Container) RETURN count(n) as count"
        assert args[1] == {"limit": 10}


@pytest.fixture
def mock_driver():
    with patch("app.infrastructure.graph.neo4j_client.GraphDatabase") as mock_gdb:
        mock_driver_instance = MagicMock()
        mock_gdb.driver.return_value = mock_driver_instance
        yield mock_driver_instance
