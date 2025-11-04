# models.py
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import uuid

# ---------- Payloads ----------

class EmbeddingPayload(BaseModel):
    kind: Literal["embedding"] = "embedding"
    vector: List[float] = Field(..., description="Raw or normalized Embedding.")
    model: str = Field(..., description="Used Model name.")
    dim: Optional[int] = Field(None, description="Dimensionality (auto if not pass).")
    note: Optional[str] = None

    @field_validator("dim", mode="before")
    @classmethod
    def infer_dim(cls, v, info):
        if v is None:
            vec = info.data.get("vector")
            if isinstance(vec, list):
                return len(vec)
        return v

class JsonPayload(BaseModel):
    kind: Literal["json"] = "json"
    data: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary JSON response.")

class TextPayload(BaseModel):
    kind: Literal["text"] = "text"
    text: str
    mime_type: str = Field("text/plain", description="Text MIME Type (text/plain, text/markdown).")
    model: Optional[str] = Field(None, description="Model text generator (if applicable).")

class FilePayload(BaseModel):
    kind: Literal["file"] = "file"
    uri: str = Field(..., description="Source file (file://, s3://, http://).")
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = Field(None, description="Integrity Hash.")
    # Opcional: contenido inline (evítalo para archivos grandes)
    content_b64: Optional[str] = Field(
        None, description="Base64 Content (just small blobs/opcional)."
    )

GuardialPayload = Union[EmbeddingPayload, JsonPayload, TextPayload, FilePayload]

# ---------- Task traces ----------

class TaskLog(BaseModel):
    name: str
    status: Literal["ok", "warn", "error"] = "ok"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("duration_ms", mode="before")
    @classmethod
    def compute_duration(cls, v, info):
        if v is None:
            s = info.data.get("started_at")
            e = info.data.get("ended_at")
            if isinstance(s, datetime) and isinstance(e, datetime):
                return int((e - s).total_seconds() * 1000)
        return v

# ---------- Guardial response ----------

class GuardialResponse(BaseModel):
    # Identidad / estado
    id: Optional[str] = Field(None, description="Correlationable ID (trace_id, job_id, etc.)")
    ok: bool = True
    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    status_code: Optional[int] = Field(None, description="HTTP/semántico Code if applicable.")
    question: str = Field(
        description='Input needed from the user to generate the plan'
    )

    # Observabilidad / contexto
    source: str = Field(..., description="Source of truth (guardial/agent/nodo).")
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None
    tasks: List[TaskLog] = Field(default_factory=list)

    # Datos
    payload: GuardialPayload
    meta: Dict[str, Any] = Field(default_factory=dict, description="Extra Metadata.")
    errors: List[str] = Field(default_factory=list)

    # ---------- Building Helpers ----------

    @classmethod
    def from_embedding(
        cls,
        vector: List[float],
        model: str,
        *,
        source: str,
        id: Optional[str] = None,
        tasks: Optional[List[TaskLog]] = None,
        meta: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        ok: bool = True,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> "GuardialResponse":
        return cls(
            id=id,
            ok=ok,
            status_code=status_code,
            source=source,
            duration_ms=duration_ms,
            tasks=tasks or [],
            payload=EmbeddingPayload(vector=vector, model=model, note=note),
            meta=meta or {},
        )

    @classmethod
    def from_json(
        cls,
        data: Dict[str, Any],
        *,
        source: str,
        id: Optional[str] = None,
        tasks: Optional[List[TaskLog]] = None,
        meta: Optional[Dict[str, Any]] = None,
        ok: bool = True,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        errors: Optional[List[str]] = None,
    ) -> "GuardialResponse":
        return cls(
            id=id,
            ok=ok,
            status_code=status_code,
            source=source,
            duration_ms=duration_ms,
            tasks=tasks or [],
            payload=JsonPayload(data=data),
            meta=meta or {},
            errors=errors or [],
        )

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        source: str,
        mime_type: str = "text/plain",
        model: Optional[str] = None,
        id: Optional[str] = None,
        tasks: Optional[List[TaskLog]] = None,
        meta: Optional[Dict[str, Any]] = None,
        ok: bool = True,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> "GuardialResponse":
        return cls(
            id=id,
            ok=ok,
            status_code=status_code,
            source=source,
            duration_ms=duration_ms,
            tasks=tasks or [],
            payload=TextPayload(text=text, mime_type=mime_type, model=model),
            meta=meta or {},
        )

    @classmethod
    def from_file(
        cls,
        uri: str,
        *,
        source: str,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        sha256: Optional[str] = None,
        content_b64: Optional[str] = None,
        id: Optional[str] = None,
        tasks: Optional[List[TaskLog]] = None,
        meta: Optional[Dict[str, Any]] = None,
        ok: bool = True,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> "GuardialResponse":
        return cls(
            id=id,
            ok=ok,
            status_code=status_code,
            source=source,
            duration_ms=duration_ms,
            tasks=tasks or [],
            payload=FilePayload(
                uri=uri,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                sha256=sha256,
                content_b64=content_b64,
            ),
            meta=meta or {},
        )

# ---------- MCP Data Models ----------

class SemanticSignals(BaseModel):
    """Semantic signals from vector store analysis"""
    pii_detected: bool = False
    secrets_found: List[str] = Field(default_factory=list)
    scope_creep: float = 0.0
    bias_indicators: List[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    confidence_score: float = 0.0

class GuardialInputV1(BaseModel):
    """Input schema for guardial.evaluate MCP tool"""
    task_id: str
    context_id: str
    user_id: str
    policy_refs: List[str] = Field(default_factory=list)
    expected_behaviors_ref: Optional[str] = None
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    semantic_signals: SemanticSignals = Field(default_factory=SemanticSignals)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PolicyViolation(BaseModel):
    """Represents a policy violation"""
    policy_name: str
    rule_name: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    violated_content: Optional[str] = None
    remediation: Optional[str] = None

class SemanticViolation(BaseModel):
    """Represents a semantic violation"""
    violation_type: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    confidence: float
    detected_content: Optional[str] = None
    remediation: Optional[str] = None

class RiskAssessment(BaseModel):
    """Risk assessment details"""
    overall_risk: float
    policy_risk: float
    semantic_risk: float
    risk_factors: List[str] = Field(default_factory=list)
    mitigation_suggestions: List[str] = Field(default_factory=list)

class AuditReport(BaseModel):
    """Structured audit report"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    policy_violations: List[PolicyViolation] = Field(default_factory=list)
    semantic_violations: List[SemanticViolation] = Field(default_factory=list)
    risk_assessment: RiskAssessment
    remediation_suggestions: List[str] = Field(default_factory=list)

class ComplianceTrace(BaseModel):
    """Compliance trace for audit trail"""
    rules_evaluated: List[str] = Field(default_factory=list)
    decision_path: List[str] = Field(default_factory=list)
    timestamps: Dict[str, datetime] = Field(default_factory=dict)
    evaluation_context: Dict[str, Any] = Field(default_factory=dict)

class GuardialEvaluationResponse(BaseModel):
    """Response from guardial.evaluate MCP tool"""
    decision: Literal["allow", "deny", "review"]
    deviation_score: float
    audit_report: AuditReport
    compliance_trace: ComplianceTrace
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uncertain: bool = False
    processing_time_ms: Optional[int] = None
    
    # Additional metadata
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluator_version: str = "1.0.0"
    policy_version: Optional[str] = None