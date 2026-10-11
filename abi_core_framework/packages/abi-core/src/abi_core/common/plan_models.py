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
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


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
    # No max_length on purpose: a too-long title must not fail validation of
    # the whole plan — clean_title() trims it instead. Shown to the user in
    # the plan review card; see
    # .abi/specs/not-implemented/ux/chainlit-plan-review-card.md (B1).
    title: Optional[str] = Field(
        None,
        description="Short label for this task shown to the user (max 60 characters), in the same language as the user's request",
    )
    description: str = Field(..., min_length=10, max_length=500, description="Clear, actionable instruction for the executing agent")
    dependencies: List[str] = Field(default_factory=list, description="task_ids this task depends on")
    target: Optional[TaskTarget] = Field(None, description="What this task produces — tag identifies the artifact")
    direct_tool: Optional[Literal["write_pdf"]] = Field(
        None,
        description=(
            "Set ONLY when this task's deliverable is a fixed, simple artifact "
            "producible by a known framework tool without any generated/executed "
            "code — today: a PDF. When set, the Planner executes it directly "
            "(no ephemeral agent). See .abi/specs/planner-direct-tool-pdf.md."
        ),
    )

    @field_validator("dependencies")
    @classmethod
    def dedupe_dependencies(cls, v: List[str]) -> List[str]:
        """Dedupe while preserving order — reproduced live 2026-09-27: the
        model (under invoke_structured's schema constraint) repeated a
        dependency id within this list (e.g. ["task_1", "task_1"] instead of
        ["task_1"]). Nothing downstream caught it: build_workflow's edge
        loop iterates dependencies faithfully, so a duplicate id added the
        SAME edge twice — and LangGraph fires a node once per incoming edge
        instance, not once per distinct predecessor, so a task with a
        duplicated dependency ran twice while a sibling task's A2A
        connection got raced out from under it. Same LLM-repeats-a-list-
        element failure family as the earlier "5 identical tasks" bug, just
        one level deeper (inside a field instead of the top-level tasks
        array) — no schema-level guard existed for either until now."""
        seen = set()
        deduped = []
        for dep in v:
            if dep not in seen:
                seen.add(dep)
                deduped.append(dep)
        return deduped

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = " ".join(v.split()).strip(" .")
        if not v:
            return None
        return v if len(v) <= 60 else v[:59].rstrip() + "…"

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
    # Not model-chosen — the Planner overwrites both fields deterministically
    # after this schema is filled (see AbiPlannerAgent._call_llm). Kept
    # `Optional`/description-free rather than removed so existing UI code
    # reading `plan.get("methodology")` keeps working; a field description
    # here previously read as an implicit instruction and caused the model
    # to volunteer methodology names on its own (e.g. "Polya") even with no
    # prompt asking for one — see _call_llm's comment for the live repro.
    methodology: Optional[str] = None
    methodology_rationale: Optional[str] = Field(None, max_length=300)
    # The SDD Phase 2 design (TechnicalDesign.model_dump()), set by the
    # Planner after apply_technical_design — never by the model. Hidden from
    # the JSON schema the model decodes against: a visible field gets filled
    # on the model's own initiative (same lesson as `methodology` above).
    # Kept so the plan reaches the Orchestrator and the reviewer with every
    # file's role, not only its dependencies. Spec: ephemeral-reviewer-
    # pipeline/02-ephemeral-reviewer/02.1-project-folder-and-full-plan.md
    technical_design: SkipJsonSchema[Optional[Dict[str, Any]]] = None


class PlannerOutput(BaseModel):
    """Top-level planner response — either a plan or clarification questions."""
    status: Literal["ready", "needs_clarification"]
    plan: Optional[Plan] = None
    questions: Optional[List[ClarificationQuestion]] = None
    partial_understanding: Optional[str] = Field(None, max_length=300)

    def to_dict(self) -> dict:
        """Convert to dict matching the format downstream expects."""
        return self.model_dump(exclude_none=True)


# ── Technical design (SDD Phase 2 — "Plan técnico") ─────────────────
# Decided BEFORE task generation, in its own structured call, so the
# direction of file dependencies is reasoned about explicitly instead of
# improvised in the same breath as inventing filenames. Reproduced live
# 2026-10-01: a 5-file Pac-Man plan declared pacman.py (the entry point)
# with NO dependencies and player/ghosts/pellets depending ON it — backwards.
# pacman.py ran first, wrote a monolithic game, and the support modules it
# should have imported were never used. See
# .abi/specs/not-implemented/sdd-pipeline/01-planner-spec-plan-tasks-cycle.md.


class FileDesignUnit(BaseModel):
    """One file in the technical design and its role/dependencies."""
    filename: str = Field(..., description="Real filename, e.g. 'pacman.py'")
    role: Literal["entry_point", "module", "documentation"] = Field(
        ...,
        description=(
            "entry_point: the file that is run and orchestrates the rest. "
            "module: support code imported by the entry_point or another module. "
            "documentation: describes other files of this same plan."
        ),
    )
    responsibility: str = Field(..., max_length=200, description="What this file does, one line")
    depends_on: List[str] = Field(
        default_factory=list,
        description=(
            "Other filenames of THIS plan that this file must import or reference. "
            "If file X uses a class/function defined in file Y, X depends on Y — never "
            "the reverse. The entry_point depends on every module it uses. A module "
            "depends on nothing unless it needs another module. A documentation file "
            "depends on every file it describes."
        ),
    )


class TechnicalDesign(BaseModel):
    """SDD Phase 2 output: the set of files and who depends on whom."""
    # max_length=5 enforced at decode time (schema-constrained), not after:
    # parse_plan's _enforce_atomic_tasks truncates to 5 tasks, so a 6-file
    # design silently lost its last file — reproduced live 2026-10-03, the
    # README (documentation, always last since it depends on everything).
    files: List[FileDesignUnit] = Field(..., min_length=1, max_length=5)


def apply_technical_design(plan: Plan, design: TechnicalDesign) -> List[str]:
    """Overwrite each task's `dependencies` from the technical design.

    Deterministic, not a second LLM decision: the direction of dependencies
    was already decided in Phase 2 — Phase 3 (task generation) must not get
    a chance to re-invent it. Tasks are matched to design files by
    `target.tag` == `filename`. Tasks with no matching design entry keep the
    dependencies the model gave them (logged as a warning by the caller).

    Returns a list of human-readable warnings (unmatched tasks, design
    dependencies pointing at files no task produces).
    """
    warnings: List[str] = []
    original = {t.task_id: list(t.dependencies) for t in plan.tasks}
    tag_to_task = {
        t.target.tag: t.task_id
        for t in plan.tasks
        if t.target and t.target.tag
    }
    design_by_name = {f.filename: f for f in design.files}

    for task in plan.tasks:
        tag = task.target.tag if task.target else None
        unit = design_by_name.get(tag) if tag else None
        if unit is None:
            warnings.append(
                f"{task.task_id} (target={tag!r}) has no entry in the technical "
                f"design — keeping model-declared dependencies {task.dependencies}"
            )
            continue
        deps = []
        for dep_file in unit.depends_on:
            dep_task = tag_to_task.get(dep_file)
            if dep_task is None:
                warnings.append(
                    f"{task.task_id}: design says {tag!r} depends on {dep_file!r}, "
                    f"but no task produces it — dropped"
                )
            elif dep_task != task.task_id and dep_task not in deps:
                deps.append(dep_task)
        task.dependencies = deps

    # A cycle (A depends on B, B on A) would leave those LangGraph nodes
    # waiting on each other forever — never executed, no error. Revert to
    # the model's own dependencies rather than ship an unrunnable graph.
    if _has_cycle({t.task_id: t.dependencies for t in plan.tasks}):
        for task in plan.tasks:
            task.dependencies = original[task.task_id]
        warnings.append("technical design produced a dependency cycle — reverted to model-declared dependencies")

    return warnings


def _has_cycle(graph: dict) -> bool:
    visiting, done = set(), set()

    def visit(node):
        if node in done:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        if any(visit(d) for d in graph.get(node, []) if d in graph):
            return True
        visiting.discard(node)
        done.add(node)
        return False

    return any(visit(n) for n in graph)
