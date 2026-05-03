from __future__ import annotations

import logging
import re
from typing import Any

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError

from app.domain.exceptions import GraphDatabaseError
from app.utils.config import get_config

logger = logging.getLogger(__name__)

_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_valid_label(label: str) -> bool:
    return bool(_VALID_IDENTIFIER.match(label))


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self.uri = uri
        self.user = user
        self.database = database
        try:
            self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
        except DriverError as e:
            raise GraphDatabaseError(f"Failed to connect to Neo4j at {uri}: {e}")

    @classmethod
    def from_config(cls) -> "Neo4jClient":
        config = get_config()
        neo4j_config = config.neo4j
        return cls(
            uri=str(neo4j_config.uri),
            user=str(neo4j_config.username),
            password=str(neo4j_config.password),
            database=str(neo4j_config.database),
        )

    def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        if not _is_valid_label(label):
            raise ValueError(f"Invalid label: {label!r}. Labels must match {_VALID_IDENTIFIER.pattern}")
        cypher = f"""
        MERGE (n:`{label}` {{id: $node_id}})
        SET n += $props
        """
        with self._session() as session:
            session.run(cypher, node_id=node_id, props=properties)

    def upsert_relationship(
        self,
        rel_type: str,
        rel_id: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> None:
        if not _is_valid_label(rel_type):
            raise ValueError(f"Invalid relationship type: {rel_type!r}. Must match {_VALID_IDENTIFIER.pattern}")
        cypher = f"""
        MATCH (a {{id: $from_id}})
        MATCH (b {{id: $to_id}})
        MERGE (a)-[r:`{rel_type}` {{id: $rel_id}}]->(b)
        SET r += $props
        """
        with self._session() as session:
            session.run(cypher, rel_id=rel_id, from_id=from_id, to_id=to_id, props=properties)

    def clear_extraction(self, task_id: str) -> None:
        cypher = """
        MATCH (n {extraction_task_id: $task_id})
        DETACH DELETE n
        """
        with self._session() as session:
            session.run(cypher, task_id=task_id)

    def query(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._session() as session:
            result = session.run(cypher, params)
            records = []
            for record in result:
                native_record = {}
                for key in record.keys():
                    value = record[key]
                    if hasattr(value, "to_native_type"):
                        native_record[key] = value.to_native_type()
                    else:
                        native_record[key] = value
                records.append(native_record)
            return records

    def close(self) -> None:
        self.driver.close()

    def _session(self):
        return self.driver.session(database=self.database)
