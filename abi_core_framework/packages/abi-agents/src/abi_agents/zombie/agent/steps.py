"""Zombie Agent — Steps.

DAG:
  gather_context → analyze_and_execute → synthesize_and_report
"""

import json
import os
import time

from app import agent
from abi_core.common.utils import abi_logging
from abi_agents.zombie.agent.zombie import ZOMBIE_TOOLS
from abi_agents.zombie.agent.config.config import config
from abi_agents.zombie.agent import lifecycle


def _file_hash(path: str) -> str:
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def _is_step_limit(error: Exception) -> bool:
    """LangGraph's recursion (step) limit, by type or message."""
    return type(error).__name__ == "GraphRecursionError" or "Recursion limit" in str(error)


def _written_files(context: dict) -> list:
    """Files in the workspace this task wrote: new ones, or inputs it changed."""
    hashes = context.get("artifact_hashes") or {}
    out = []
    if not os.path.isdir(config.WORKSPACE):
        return out
    for name in sorted(os.listdir(config.WORKSPACE)):
        path = os.path.join(config.WORKSPACE, name)
        if os.path.isfile(path) and (path not in hashes or _file_hash(path) != hashes[path]):
            out.append(name)
    return out


def _contract_key(process_context: dict, task_id: str) -> str:
    """Session-store key for a task's inter-task contract.

    PLAN_CONTEXT_ID is the conversation's id, shared by every plan in the
    chat, and task ids repeat across plans (task_1..task_N). The plan's
    run_id (written by the Orchestrator in process_context) keeps one plan
    from reading another plan's contract. Without it (older Orchestrator),
    fall back to the old key.
    """
    run_id = (process_context or {}).get("run_id")
    if run_id:
        return f"{config.PLAN_CONTEXT_ID}:{run_id}:{task_id}"
    return f"{config.PLAN_CONTEXT_ID}:{task_id}"


def _contract_summary(contract: dict) -> str:
    """One log line per contract: file → public names. Lets a run show what
    a task actually saw from its dependencies, so "the model ignored the
    contract" and "the contract never reached it" can be told apart."""
    parts = []
    for filename, fc in (contract or {}).get("files", {}).items():
        names = [c["name"] for c in fc.get("classes", [])] + [f["name"] for f in fc.get("functions", [])]
        parts.append(f"{filename} → {', '.join(names) or '(nothing public)'}")
    return "; ".join(parts) or "(empty)"


@agent.step(
    name="gather_context",
    input_map={"query": "$input.query"},
)
async def gather_context(query):
    """Phase 1: Pull specific artifacts from MinIO, prepare workspace."""
    from abi_core.common.context_loader import load_agent_context

    abi_logging(f"Loading context to start execution...")

    ctx = await load_agent_context(
        artifact_keys=config.ARTIFACT_KEYS if config.ARTIFACT_KEYS else None,
        workspace=config.WORKSPACE,
    )

    # process-awareness.md (Tier 3) — read back the plan-wide blob the
    # Orchestrator wrote (session_backend, keyed by PLAN_CONTEXT_ID, NOT
    # this task's own CONTEXT_ID). Deterministic fetch, not an LLM tool.
    process_context = {}
    dependency_contracts = {}
    dependency_tdds = {}   # filename -> TDD (code_tdd.build_tdd) of each dependency file
    if config.PLAN_CONTEXT_ID:
        session_ctx = await agent.get_session_context(config.PLAN_CONTEXT_ID)
        process_context = session_ctx.get("process_context", {})

        # Inter-task integration report: each dependency writes its own
        # contract (classes/functions it exposes, extracted by ast — see
        # synthesize_and_report) to its own key, keyed by
        # _contract_key() — "{PLAN_CONTEXT_ID}:{run_id}:{task_id}" — never a shared blob, so two
        # sibling tasks finishing in parallel (confirmed real since the
        # LangGraph join fix) can't clobber each other's write.
        my_task_id = config.CONTEXT_ID
        my_deps = next(
            (t.get("dependencies", []) for t in process_context.get("tasks", [])
             if t.get("task_id") == my_task_id),
            [],
        )
        abi_logging(f"[📜] {my_task_id} dependencies: {my_deps or 'none'}")
        for dep_task_id in my_deps:
            dep_ctx = await agent.get_session_context(_contract_key(process_context, dep_task_id))
            contract = dep_ctx.get("contract")
            if dep_ctx.get("tdd"):
                dependency_tdds.update(dep_ctx["tdd"])
            if contract:
                dependency_contracts[dep_task_id] = contract
                abi_logging(f"[📜] Contract from {dep_task_id}: {_contract_summary(contract)}")
            else:
                abi_logging(
                    f"[📜] No contract from {dep_task_id} in the session store — "
                    f"this task generates without knowing what that file exposes",
                    level="warning",
                )
    else:
        abi_logging("[📜] No PLAN_CONTEXT_ID — dependency contracts unavailable", level="warning")

    # Content hash of every input artifact, so synthesize_and_report can
    # tell an input this task left alone (skip it) from one it rewrote
    # (upload it). The integration reviewer rewrites the very files it
    # receives; excluding inputs by path alone silently dropped them.
    artifact_hashes = {p: _file_hash(p) for p in ctx["artifacts"]}

    return {
        "query": query,
        "workspace": config.WORKSPACE,
        "artifacts": ctx["artifacts"],
        "artifact_hashes": artifact_hashes,
        "tools_available": config.TOOL_NAMES,
        "system_prompt": config.SYSTEM_PROMPT,
        "process_context": process_context,
        "dependency_contracts": dependency_contracts,
        "dependency_tdds": dependency_tdds,
    }


async def _plan_info(process_context: dict) -> dict:
    """This task's file, role and responsibility, the plan's files and entry
    point, from the plan the Orchestrator wrote to the run's project folder
    (with its technical design). Falls back to process_context for the
    objective; anything missing is left out."""
    info = {"objective": process_context.get("objective", "")}
    run_id = process_context.get("run_id")
    if not run_id:
        return info
    try:
        from abi_core.common import project_store
        plan = await project_store.load_json(run_id, "plan", "plan.json")
    except Exception as e:
        abi_logging(f"[⚠️] Plan not readable from the project folder: {e}", level="warning")
        return info
    tasks = plan.get("tasks") or []
    mine = next((t for t in tasks if t.get("task_id") == config.CONTEXT_ID), {})
    filename = (mine.get("target") or {}).get("tag", "")
    design = (plan.get("technical_design") or {}).get("files") or []
    unit = next((f for f in design if f.get("filename") == filename), {})
    info.update({
        "objective": plan.get("objective") or info["objective"],
        "filename": filename,
        "role": unit.get("role", ""),
        "responsibility": unit.get("responsibility", ""),
        "plan_files": [f.get("filename") for f in design if f.get("filename")]
        or [(t.get("target") or {}).get("tag") for t in tasks if (t.get("target") or {}).get("tag")],
        "entry_point": next((f.get("filename") for f in design if f.get("role") == "entry_point"), ""),
    })
    return info


@agent.step(
    name="analyze_and_execute",
    input_map={"context": "$gather_context", "query": "$input.query"},
    depends_on=["gather_context"],
    tools=["write_file"],
    timeout=config.EXECUTION_TIMEOUT,
    max_retries=1,
)
async def analyze_and_execute(context, query):
    """Phase 2: LLM autonomous execution with tools, enriched with memory context."""
    from abi_core.agent.llm_provider import invoke
    from abi_core.common.context_loader import build_execution_prompt

    # Inject memory context if AMS is available
    memory_context = ""
    if config.AGENT_MEMORY_URL and config.CONTEXT_ID:
        from abi_core.memory import recall_memory_context

        memory_context = await recall_memory_context(
            query=query,
            context_id=config.CONTEXT_ID,
            memory_url=config.AGENT_MEMORY_URL,
        )
        if memory_context:
            abi_logging(f"[🧠] Memory context injected ({len(memory_context)} chars)")

    # No tool list in the message: the model gets the tools declared, and
    # the role prompt says which to use for what (user decision 2026-10-10).
    execution_prompt = build_execution_prompt(
        query=query,
        artifacts=context.get("artifacts", []),
        workspace=config.WORKSPACE,
    )

    # Role prompt (ephemeral-reviewer-pipeline spec 04, prompt 1): fixed role,
    # then "# This task" filled from the plan in the run's project folder and
    # its technical design. Contracts: what each dependency's file actually
    # exposes (ast-extracted signatures) and its spec, so the model imports
    # prior work instead of reimplementing it (live 2026-09-29 without it).
    # The texts live in abi_core.common.prompts.code_agent.
    from abi_core.common.integration_review import SANDBOX_THIRD_PARTY
    from abi_core.common.prompts.code_agent import build_code_agent_system_prompt
    dependency_contracts = context.get("dependency_contracts") or {}
    if dependency_contracts:
        abi_logging(
            "[📜] Dependency contracts in the prompt: "
            + "; ".join(_contract_summary(c) for c in dependency_contracts.values())
        )
    plan_info = await _plan_info(context.get("process_context") or {})
    system_prompt = build_code_agent_system_prompt(
        task_description=config.SYSTEM_PROMPT,
        workspace=config.WORKSPACE,
        sandbox_modules=sorted(SANDBOX_THIRD_PARTY),
        dependency_contracts=dependency_contracts,
        dependency_tdds=context.get("dependency_tdds"),
        memory_context=memory_context,
        **plan_info,
    )

    # Per-chunk grace period, not the whole step's budget (config.
    # EXECUTION_TIMEOUT, 600s default) — bounds how long a SINGLE stream
    # chunk can take before it's treated as stalled, not the whole
    # multi-turn tool-calling exchange. Without this, Path B of invoke()
    # has zero protection against a frozen event loop — reproduced live
    # 2026-09-29 (two ephemerals under real concurrent Ollama load, zero
    # heartbeat ticks over the full 600s step timeout).
    # Tool-call budget sized to the work, not a fixed number: reading each
    # input file and writing each output costs ~2 tool calls per file, and
    # every call is 2 graph steps. A one-file task keeps the old 10; the
    # integration reviewer (5 inputs) gets ~30. Capped as a guard against
    # endless loops. Same lesson as the 600s timeout: a fixed limit sized
    # for the common case cuts off legitimate larger work.
    # Floor 30 (15 tool calls), user decision 2026-10-09: on Gemini a code
    # agent writes its file and then checks it with run_shell — live, 5
    # calls hit the old floor of 10 right after write_file, and the file was
    # lost.
    n_inputs = len(context.get("artifacts") or [])
    recursion_limit = min(60, max(30, 2 * (2 * n_inputs + 4)))

    try:
        # Work record + kept conversation: the code agent answers the
        # reviewer later from what it did (02.2), not by re-reading its file.
        lifecycle.work_record.update({
            "task": query,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "inputs_read": [os.path.basename(p) for p in context.get("artifacts", [])],
            "dependency_contracts": sorted(context.get("dependency_contracts") or {}),
            "dependency_specs": sorted(context.get("dependency_tdds") or {}),
        })
        result = await invoke(
            config.LLM_CONFIG, execution_prompt,
            tools=ZOMBIE_TOOLS, system_prompt=system_prompt,
            required_tools=["write_file"],
            call_timeout=120.0,
            recursion_limit=recursion_limit,
            thread_id=lifecycle.GENERATION_THREAD,
            checkpointer=lifecycle.generation_memory(),
        )
    except Exception as e:
        # Integration reviewer only (user decision, 2026-10-04): files it
        # already rewrote are still worth keeping if it stops early — the
        # Orchestrator re-runs the integration review on them, so a partial
        # repair is judged by code, not trusted. Live 2026-10-04 the
        # reviewer rewrote 1 of 5 files, hit a step limit, and all of it was
        # lost. Any other task still fails as before: a half-written
        # deliverable would pass the Phase 2.5 existence check and mislead.
        #
        # Code agent with a reviewer in its plan (user decision 2026-10-09):
        # if it hit the step limit after writing its file, keep the file —
        # the reviewer and the Orchestrator's verification judge it. Live
        # 2026-10-09 five agents wrote their files, hit the limit while
        # checking them, and all five were lost. Without a reviewer, nothing
        # would judge a half-checked file, so it still fails.
        from abi_core.common.integration_review import REVIEW_TASK_PREFIX
        if (config.CONTEXT_ID or "").startswith(REVIEW_TASK_PREFIX):
            abi_logging(
                f"[⚠️] Reviewer stopped early ({type(e).__name__}: {e}) — "
                "uploading what it already rewrote for re-review",
                level="warning",
            )
            result = f"Partial repair — stopped early: {e}"
        elif (_is_step_limit(e) and (context.get("process_context") or {}).get("reviewer")
              and _written_files(context)):
            abi_logging(
                f"[⚠️] Step limit reached after writing {_written_files(context)} — "
                "keeping the file for the reviewer to judge",
                level="warning",
            )
            lifecycle.work_record["stopped_early"] = str(e)
            result = f"Stopped at the step limit after writing the file: {e}"
        else:
            raise
    
    abi_logging(f"[✅] Query: {query} Results: {result}")
    
    return {"result": result, "query": query}


@agent.step(
    name="synthesize_and_report",
    input_map={"execution_result": "$analyze_and_execute", "context": "$gather_context"},
    depends_on=["analyze_and_execute"],
)
async def synthesize_and_report(execution_result, context):
    """Phase 3: Upload generated artifacts and flush logs."""
    from abi_core.common.artifact_store import upload_workspace_artifacts

    uploaded_artifacts = []
    status = "completed"

    try:
        # Skip inputs this task didn't change; upload the ones it rewrote.
        hashes = context.get("artifact_hashes") or {}
        unchanged = [
            p for p in context.get("artifacts", [])
            if p not in hashes or _file_hash(p) == hashes[p]
        ]
        rewritten = [p for p in context.get("artifacts", []) if p not in unchanged]
        if rewritten:
            abi_logging(f"[📝] Rewrote {len(rewritten)} input file(s): {[os.path.basename(p) for p in rewritten]}")
        uploaded_artifacts = await upload_workspace_artifacts(
            agent_name=config.AGENT_NAME,
            workspace=config.WORKSPACE,
            exclude=unchanged,
        )
    except Exception as e:
        status = "incompleted"
        # Python 3 unbinds `e` when the except block ends; the result below
        # used str(e) and raised its own UnboundLocalError on top.
        upload_error = str(e)
        abi_logging(f"[❌] Error synthesize_and_report: {e}")

    # Project folder (ephemeral-reviewer-pipeline 02.1): the deliverables
    # also go to projects/<run_id>/code|docs. The per-agent keys above stay —
    # today's Orchestrator builds the user's links from them. Not for the
    # integration reviewer: its rewrites must not overwrite the code agents'
    # originals in code/ (the reviewer's own flow is sub-spec 02.3).
    from abi_core.common.integration_review import REVIEW_TASK_PREFIX
    run_id = (context.get("process_context") or {}).get("run_id")
    to_project = bool(run_id) and not (config.CONTEXT_ID or "").startswith(REVIEW_TASK_PREFIX)
    if to_project and uploaded_artifacts:
        from abi_core.common import project_store
        for art in uploaded_artifacts:
            filename = art.get("filename", "")
            try:
                with open(os.path.join(config.WORKSPACE, filename), "rb") as fh:
                    await project_store.save(
                        run_id, project_store.area_for(filename), filename, fh.read(),
                        metadata={"agent": config.AGENT_NAME, "task_id": config.CONTEXT_ID or ""},
                    )
            except Exception as e:
                abi_logging(f"[⚠️] {filename} not copied to project folder: {e}", level="warning")

    # Inter-task integration report — deterministic contract of what this
    # task's .py files actually expose, written to this task's OWN key
    # (never a shared blob two parallel siblings could clobber). See
    # gather_context/analyze_and_execute for the read side.
    if config.PLAN_CONTEXT_ID and uploaded_artifacts:
        # os is imported at module level — a local `import os` here made
        # `os` local to the whole function, so the "Rewrote" log above
        # raised UnboundLocalError and the upload failed (live 2026-10-05).
        from abi_core.common.context_loader import extract_python_contract

        # Keyed by filename — a dependent needs the module name to write
        # `from player import PacMan`, not just the class signature. The old
        # merged {"classes", "functions"} lost which file each came from.
        contract = {"files": {}}
        for art in uploaded_artifacts:
            filename = art.get("filename", "")
            if filename.endswith(".py"):
                file_contract = extract_python_contract(os.path.join(config.WORKSPACE, filename))
                if file_contract.get("classes") or file_contract.get("functions"):
                    contract["files"][filename] = file_contract
        if contract["files"]:
            await agent.update_session_context(
                _contract_key(context.get("process_context"), config.CONTEXT_ID), {"contract": contract}
            )
            abi_logging(f"[📜] Contract written for {config.CONTEXT_ID}: {_contract_summary(contract)}")
        else:
            abi_logging(
                f"[📜] No contract written for {config.CONTEXT_ID}: its .py files expose no public "
                f"classes or functions (dependents will get nothing)",
                level="warning",
            )

        # Code agent TDD — one per .py this task delivered. Built against every
        # .py in the workspace (this task's own and its dependencies'), so the
        # early findings ("assumes" vs the dependencies' "exposes") are seen
        # here, before the integration review. Recorded only; triggers nothing.
        # Spec: .abi/specs/not-implemented/ephemeral-reviewer-pipeline/01-code-agent-tdd.md
        try:
            from abi_core.common.code_tdd import build_tdd
            from abi_core.common.artifact_store import ArtifactStore

            workspace_py = {}
            for name in os.listdir(config.WORKSPACE):
                if name.endswith(".py"):
                    with open(os.path.join(config.WORKSPACE, name), "r", errors="replace") as fh:
                        workspace_py[name] = fh.read()
            answer = str(execution_result.get("result", ""))
            tdds = {
                art["filename"]: build_tdd(art["filename"], workspace_py, answer)
                for art in uploaded_artifacts if art.get("filename", "").endswith(".py")
                and art["filename"] in workspace_py
            }
            lifecycle.work_record["spec"] = tdds
            if tdds:
                await agent.update_session_context(
                    _contract_key(context.get("process_context"), config.CONTEXT_ID), {"tdd": tdds}
                )
                store = ArtifactStore()
                for name, tdd in tdds.items():
                    # The TDD is the code agent's spec: projects/<run_id>/spec/
                    # (02.1). Without a run_id (older Orchestrator), the old
                    # per-agent key.
                    if to_project:
                        from abi_core.common import project_store
                        await project_store.save_json(
                            run_id, "spec", f"{name}.tdd.json", tdd,
                            metadata={"agent": config.AGENT_NAME, "origin": "code-agent-tdd"},
                            store=store,
                        )
                    else:
                        await store.upload(
                            f"{config.AGENT_NAME}/{name}.tdd.json",
                            json.dumps(tdd, ensure_ascii=False, indent=2).encode("utf-8"),
                            metadata={"agent": config.AGENT_NAME, "origin": "code-agent-tdd"},
                        )
                    abi_logging(
                        f"[📐] TDD {name}: early_findings={len(tdd['early_findings'])} "
                        f"resources={len(tdd['resources'])} role={tdd['role'].get('flags', [])} "
                        f"model_fields_missing={tdd['model_fields_missing']}"
                    )
        except Exception as e:
            abi_logging(f"[⚠️] Code agent TDD failed (non-blocking): {e}", level="warning")

    # Persist result summary to working memory for subsequent tasks
    if config.AGENT_MEMORY_URL and config.CONTEXT_ID:
        from abi_core.memory import add_short_term_memory

        filenames = [a["filename"] for a in uploaded_artifacts] if uploaded_artifacts else []
        summary = (
            f"Agent '{config.AGENT_NAME}' completed task. "
            f"Result: {execution_result.get('result', '')[:200]}. "
            f"Files created: {filenames}"
        )
        if await add_short_term_memory(
            topic="task_result",
            task=config.AGENT_NAME,
            content=summary,
            context_id=config.CONTEXT_ID,
            memory_url=config.AGENT_MEMORY_URL,
        ):
            abi_logging("[🧠] Stored result in working memory")

    lifecycle.work_record.update({
        "files_written": [a["filename"] for a in uploaded_artifacts],
        "status": status,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    return {
        "status": status,
        "result": execution_result.get("result", "") if status == "completed" else upload_error,
        "uploaded_artifacts": uploaded_artifacts,
        "agent": config.AGENT_NAME,
    }


# ── Reviewer requests (02.2): answer, terminate ─────────────────

# The text lives in abi_core.common.prompts.code_agent (ANSWER_PROMPT).


@agent.step(name="answer_questions")
async def answer_questions(questions):
    """Answer the reviewer from this agent's memory. At most MAX_QUESTIONS
    in total; past that, "limit reached" without calling the model."""
    from abi_core.agent.llm_provider import invoke

    lifecycle.touch()
    asked = [str(q) for q in (questions or []) if str(q).strip()]
    room = max(0, lifecycle.MAX_QUESTIONS - lifecycle.questions_answered)
    allowed, refused = asked[:room], asked[room:]
    lifecycle.questions_answered += len(allowed)
    if refused:
        abi_logging(f"[❓] {len(refused)} question(s) over the limit of {lifecycle.MAX_QUESTIONS}: not answered")
    if not allowed:
        return {"answers": "", "answered": 0, "refused": refused,
                "note": f"question limit reached ({lifecycle.MAX_QUESTIONS})"}

    record = {k: v for k, v in lifecycle.work_record.items() if k != "spec"}
    spec = lifecycle.work_record.get("spec") or {}
    from abi_core.common.prompts.code_agent import ANSWER_PROMPT
    prompt = ANSWER_PROMPT.format(
        files=", ".join(lifecycle.work_record.get("files_written") or ["its file"]),
        record=json.dumps({**record, "spec": spec}, ensure_ascii=False, indent=2)[:12000],
        transcript=lifecycle.generation_transcript() or "(not kept)",
        questions="\n".join(f"{i}. {q}" for i, q in enumerate(allowed, 1)),
    )
    answers = await invoke(config.LLM_CONFIG, prompt, call_timeout=120.0)
    abi_logging(f"[❓] Answered {len(allowed)} reviewer question(s)")
    return {"answers": answers, "answered": len(allowed), "refused": refused}


@agent.step(name="self_destruct")
async def self_destruct(reason="reviewer done"):
    """Leave after this response is sent (main.py on_response_sent)."""
    lifecycle.request_termination(reason)
    return {"status": "terminating", "reason": reason}

