"""
Plan Models — Pydantic schemas for structured planner output.

Forces the LLM to produce clean, validated task plans instead of
free-form text that leaks reasoning into descriptions.

Usage:
    from abi_core.common.plan_models import PlannerOutput

    # Validate raw LLM JSON
    output = PlannerOutput.model_validate(parsed_json)

    # Or use with LangChain structured output
    llm_with_schema = llm.with_structured_output(PlannerOutput)
"""

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ClarificationQuestion(BaseModel):
    """A question the planner needs answered before it can plan."""
    id: str = Field(..., description="Question identifier, e.g. q1, q2")
    question: str = Field(..., max_length=300)
    type: Literal["required", "optional"] = "required"
    options: Optional[List[str]] = None


class TaskTarget(BaseModel):
    """What a task produces — used for artifact transport between agents."""
    tag: str = Field(..., description="Identifier for the artifact, e.g. 'print_message.sh' or 'sales_analysis'")
    type: Literal["file", "text", "json"] = Field("text", description="Transport mode: file=MinIO, text/json=inline A2A")


class PlanTask(BaseModel):
    """A single task in the execution plan."""
    task_id: str = Field(..., pattern=r"^task_\d+$", description="Sequential ID: task_1, task_2, ...")
    description: str = Field(..., min_length=10, max_length=500, description="Clear, actionable instruction for the executing agent")
    dependencies: List[str] = Field(default_factory=list, description="task_ids this task depends on")
    target: Optional[TaskTarget] = Field(None, description="What this task produces — tag identifies the artifact")

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str) -> str:
        """Strip LLM reasoning artifacts from task descriptions."""
        v = v.strip()
        # Remove markdown formatting
        v = re.sub(r"^#+\s*", "", v)
        v = re.sub(r"\*\*(.+?)\*\*", r"\1", v)
        v = re.sub(r"\*(.+?)\*", r"\1", v)
        v = re.sub(r"`(.+?)`", r"\1", v)
        # Remove common LLM reasoning prefixes
        reasoning_prefixes = (
            "It appears", "I will", "Let me", "Based on",
            "I need to", "First,", "To accomplish", "In order to",
            "We need to", "The task is to", "This task involves",
        )
        for prefix in reasoning_prefixes:
            if v.startswith(prefix):
                # Find the actual instruction after the reasoning
                for sep in (". ", ":\n", ": ", " — ", " - "):
                    idx = v.find(sep)
                    if idx != -1 and idx < len(v) - 20:
                        candidate = v[idx + len(sep):].strip()
                        if len(candidate) > 20:
                            v = candidate
                            break
                break
        return v.strip()


class Plan(BaseModel):
    """The execution plan with tasks and strategy."""
    objective: str = Field(..., max_length=300, description="What the plan accomplishes")
    tasks: List[PlanTask] = Field(..., min_length=1)
    execution_strategy: Literal["sequential", "parallel", "mixed"] = "sequential"


class PlannerOutput(BaseModel):
    """Top-level planner response — either a plan or clarification questions."""
    status: Literal["ready", "needs_clarification"]
    plan: Optional[Plan] = None
    questions: Optional[List[ClarificationQuestion]] = None
    partial_understanding: Optional[str] = Field(None, max_length=300)

    def to_dict(self) -> dict:
        """Convert to dict matching the format downstream expects."""
        return self.model_dump(exclude_none=True)
