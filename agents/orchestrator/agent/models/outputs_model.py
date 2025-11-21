from pydantic import BaseModel, Field, confloat, constr
from typing import List, Literal, Optional, Dict

ClassT = Literal["methodology", "static_knowledge", "time_sensitive"]
FlowT = Literal["orchestrator_answer", "worker_semantic", "planner_tool"]

class QAResult(BaseModel):
    class_: ClassT = Field(alias="class")
    confidence: confloat(ge=0.0, le=1.0)
    rationale: constr(min_length=1, max_length=200)
    extracted_entities: Optional[List[str]] = None
    proposed_flow: FlowT
    required_capabilities: Optional[List[str]] = None
    hints: Optional[Dict[str, str]] = None
