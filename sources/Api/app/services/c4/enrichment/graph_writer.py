import re
from typing import Any

from app.infrastructure.graph.neo4j_client import Neo4jClient


def normalize_logical_name(name: str) -> str:
    """Strip scheme, hyphens, 'sdk'/'api' suffixes, and domain to get logical dep name."""
    name = re.sub(r"^https?://", "", name)
    name = re.sub(r"^api\.", "", name, flags=re.IGNORECASE)
    name = re.sub(r"/v\d+.*$", "", name)
    name = re.sub(r"[-_](sdk|api)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+(sdk|api)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.(com|io|org|net)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[-_]", "_", name)
    return name.lower()


class EnrichmentGraphWriter:
    def __init__(self, driver: Any, task_id: str, run_id: str):
        self.driver = driver
        self.task_id = task_id
        self.run_id = run_id

    def upsert_node(self, type_: str, name: str,
                    props: dict[str, Any]) -> None:
        canonical = normalize_logical_name(name)
        cypher = """
        MATCH (sys:System {id: $task_id})
        MERGE (n:`%s` {canonical_name: $canonical})
        SET n.name = $name, n.task_id = $task_id,
            n.enrichment_run_id = $run_id, n += $props
        WITH n
        CALL apoc.merge.nodes([n, sys],
            {canonical_name: n.canonical_name}, {}) YIELD node
        """ % type_
        with self.driver.session() as s:
            s.run(cypher, name=name, canonical=canonical,
                  task_id=self.task_id, run_id=self.run_id, props=props)

    def upsert_edge(self, from_name: str, to_name: str,
                   relationship: str, props: dict[str, Any]) -> None:
        cypher = """
        MATCH (a {name: $from_name, task_id: $task_id})
        MATCH (b {name: $to_name, task_id: $task_id})
        MERGE (a)-[r:`%s` {run_id: $run_id}]->(b)
        SET r += $props
        """ % relationship
        with self.driver.session() as s:
            s.run(cypher, from_name=from_name, to_name=to_name,
                  run_id=self.run_id, task_id=self.task_id, props=props)

    def rollback(self) -> None:
        cypher = "MATCH (n) WHERE n.enrichment_run_id = $run_id DETACH DELETE n"
        with self.driver.session() as s:
            s.run(cypher, run_id=self.run_id)
