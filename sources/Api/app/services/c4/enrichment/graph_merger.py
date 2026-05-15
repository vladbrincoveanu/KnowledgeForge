from typing import Any

from .evidence_corpus import EvidenceCorpus
from .graph_writer import EnrichmentGraphWriter
from .json_persister import EnrichmentJSONPersister


class GraphMerger:
    def __init__(self, evidence: EvidenceCorpus, writer: EnrichmentGraphWriter,
                 persister: EnrichmentJSONPersister):
        self.evidence = evidence
        self.writer = writer
        self.persister = persister

    def add_node(self, type_: str, name: str, props: dict[str, Any]) -> None:
        self.writer.upsert_node(type_=type_, name=name, props=props)

    def add_edge(self, from_name: str, to_name: str,
                 relationship: str, props: dict[str, Any]) -> None:
        self.writer.upsert_edge(from_name=from_name, to_name=to_name,
                               relationship=relationship, props=props)

    def finalize(self, summary: dict[str, Any]) -> None:
        self.persister.finalize(summary)

    def rollback(self) -> None:
        self.writer.rollback()
        self.persister.rollback()