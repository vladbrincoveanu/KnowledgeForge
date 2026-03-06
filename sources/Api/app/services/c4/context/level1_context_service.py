"""C4 Level-1 context models.

Note: Full review/override workflow will be added in future iterations.
"""

from pydantic import BaseModel, Field


class Level1Relationship(BaseModel):
    """Relationship between C4 Level-1 entities."""

    source_entity_id: str
    relation_type: str
    target_entity_id: str
    description: str = ""


class Level1ContextResponse(BaseModel):
    """Response payload for Level-1 context endpoint."""

    system_id: str
    name: str
    description: str = ""
    owner: str = ""
    domain: str = ""
    relationships: list[Level1Relationship] = Field(default_factory=list)
