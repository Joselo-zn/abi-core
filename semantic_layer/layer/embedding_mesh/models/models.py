
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class MeshBuildingRequest(BaseModel):
    forceReload: bool = False


class MeshBuildResponse(BaseModel):
    source: str = Field(..., description="Origin:'agent_cards'")
    item: int
    model: str


class MeshUpsetItem(BaseModel):
    id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class MeshUpsertRequest(BaseModel):
    items: List[MeshUpsetItem]

    @field_validator("items")
    @classmethod
    def _no_empty(cls, v):
        if not v:
            raise ValueError(f'[!] Items must not be empty')
        return v
    

class MeshUpsertResponse(BaseModel):
    upserted: int
    model: str


class MeshSearchRequest(BaseModel):
    query: str
    topk: int = 5


class SearchHit(BaseModel):
    id: Optional[str] = None
    score: float
    text: str 
    source: str # 'agent_card' | 'upsert' 
    metadata: Optional[Dict[str, Any]] = None


class MeshSearchResponse(BaseModel):
    hits: List[SearchHit]
    model: str


class MeshResetResponse(BaseModel):
    cleared: bool


class MeshStatsResponse(BaseModel):
    model: str
    agentCardsCount: int
    upsertCount: int
