import pytest
from unittest.mock import MagicMock


class TestGraphWriterWrite:
    def test_write_calls_all_three_levels(self, mock_neo4j_client):
        from app.services.c4.graph_writer import GraphWriter
        writer = GraphWriter(mock_neo4j_client)

        c4_data = {
            "system_context": {"name": "Airbyte", "actors": [], "external_dependencies": []},
            "containers": [],
            "components": [],
            "relationships": {"context": [], "containers": []},
        }

        writer.write("task-123", c4_data)

        assert mock_neo4j_client.upsert_node.called
        node_ids = [call_args[0][1] for call_args in mock_neo4j_client.upsert_node.call_args_list]
        assert "context:Airbyte" in node_ids


class TestGraphWriterLabels:
    def test_external_system_gets_provided_evidence_nodes(self, mock_neo4j_client):
        from app.services.c4.graph_writer import GraphWriter
        writer = GraphWriter(mock_neo4j_client)

        c4_data = {
            "system_context": {
                "name": "Airbyte",
                "actors": [],
                "external_dependencies": [
                    {
                        "name": "AWS S3",
                        "type": "external_system",
                        "evidence": [
                            {"type": "package_reference", "source": "package.json", "snippet": "aws-sdk"},
                            {"type": "deployment_reference", "source": "Dockerfile", "snippet": "FROM amazonlinux"},
                        ],
                    }
                ],
            },
            "containers": [],
            "components": [],
            "relationships": {"context": [], "containers": []},
        }

        writer.write("task-456", c4_data)

        upsert_calls = mock_neo4j_client.upsert_node.call_args_list
        node_ids = [call[0][1] for call in upsert_calls]
        assert "external_system:AWS S3:0" in node_ids
        assert "evidence:external_system:AWS S3:0:0" in node_ids
        assert "evidence:external_system:AWS S3:0:1" in node_ids

        rel_calls = mock_neo4j_client.upsert_relationship.call_args_list
        rel_ids = [call[0][1] for call in rel_calls]
        assert "external_system:AWS S3:0->evidence:external_system:AWS S3:0:0" in rel_ids
        assert any(
            "PROVIDED" in str(call)
            for call in mock_neo4j_client.upsert_relationship.call_args_list
        )


class TestGraphWriterValidation:
    def test_skips_relationship_if_target_missing(self, mock_neo4j_client, caplog):
        import logging
        from app.services.c4.graph_writer import GraphWriter

        caplog.set_level(logging.WARNING)

        writer = GraphWriter(mock_neo4j_client)

        c4_data = {
            "system_context": {"name": "TestSystem", "actors": [], "external_dependencies": []},
            "containers": [{"name": "containerA"}],
            "components": [],
            "relationships": {
                "context": [],
                "containers": [
                    {"from": "containerA", "to": "containerB", "description": "uses containerB"},
                ],
            },
        }

        writer.write("task-789", c4_data)

        rel_calls = mock_neo4j_client.upsert_relationship.call_args_list
        rel_ids = [call[0][1] for call in rel_calls]
        assert "container:containerA->container:containerB" not in rel_ids
        assert any("Skipping relationship containerA->containerB" in record.message for record in caplog.records)


@pytest.fixture
def mock_neo4j_client():
    client = MagicMock()
    client.query.return_value = []
    return client