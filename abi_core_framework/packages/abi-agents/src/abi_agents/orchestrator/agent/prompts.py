"""
Orchestrator-specific prompt content.

Loose prompt strings that used to live inline inside orchestrator.py's
methods, consolidated here so every piece of text the orchestrator sends to
an LLM lives in one place. This sits alongside — not duplicating —
abi_core.common.prompts.ORCHESTRATOR_TOT_INSTRUCTIONS (the framework-shared
system prompt used to construct the agent itself); that one stays in the
shared framework file since other code may reuse it. Everything here is
specific to this agent's own reasoning-turn and synthesis calls.

config.py imports this module and exposes everything through `config.*`, so
orchestrator.py never imports prompt content directly — it only reads
config.
"""

import json


# ── Routing decision (reasoning turn, Phase 2) ──────────────────────────
#
# This call has NO system prompt otherwise (decision_llm is the bare model,
# not self.agent — ORCHESTRATOR_TOT_INSTRUCTIONS never reaches it). Structured
# as Markdown (headers + per-action sections) rather than prose paragraphs —
# reformatted 2026-09-24 after live evidence (a full, correctly-formatted
# [SYSTEM STATE] Recent conversation block reconstructed straight from Redis
# and shown to the user) that the model was receiving the right content but
# not reliably following dense-prose instructions about it. Three failure
# modes this addresses, all from the same root cause (zero framing on what
# each field is FOR / how [SYSTEM STATE] should be used):
# 1. (2026-09-15) With [SYSTEM STATE] Recent conversation present, the model
#    pattern-matched only the literal current message into `objective`,
#    ignoring relevant detail sitting right above it in the same prompt.
# 2. (2026-09-17) On a first message in a fresh session (no [SYSTEM STATE]
#    block at all), the model collapsed `objective` to a short topic-label
#    ("plan_trip") instead of the actual request — treating the field like a
#    title to summarize, not content to transfer. The `decision.objective or
#    query` fallback in orchestrator.py doesn't catch this: the field wasn't
#    empty, just useless. See .abi/specs/orchestrator-conversation-memory.md.
# 3. (2026-09-24) For action=answer_directly, the model ignored an ongoing
#    multi-turn exchange (a knock-knock joke) sitting in [SYSTEM STATE]
#    Recent conversation and replied with a generic greeting instead of
#    continuing it — verified live that the full correct history reached the
#    prompt; the model just wasn't told the block was meant to be USED for
#    continuity, only that it existed.
# No longer conditional on whether [SYSTEM STATE] is present this turn (the
# previous version appended an addendum only then) — each action's own
# section below references [SYSTEM STATE] directly; when the block is absent
# there's simply nothing there to read, which is harmless.
ROUTING_DECISION_SYSTEM_MESSAGE = """# CORE INSTRUCTIONS
You are a routing agent. Your primary task is to choose the correct action and format your output strictly according to these rules.

## 1. GLOBAL OUTPUT RULES
- **Single Field Rule:** Write your content into the ONE field required by your chosen action.
- Leave every other field at its default (empty string / null).
- NEVER write real content into a field that belongs to a different action (e.g., if action=`answer_directly`, your reply goes in `text`, never in `objective`).

## 2. HOW TO CHOOSE YOUR ACTION
Evaluate the request on its own merits without letting the output rules bias your choice.
- **Choose `answer_directly`**: For greetings, questions about you, and anything you can answer yourself in one simple reply.
- **Choose `create_plan`**: ONLY when the user asks for real work to be done, multi-step tasks, or complex requests.

## 3. ACTION-SPECIFIC PROTOCOLS

### If action = `create_plan`
- **Target Field:** Write ONLY in the `objective` field.
- **Act as a Translator:** A downstream planner will see ONLY the text you write in `objective`. It is NOT a title, category, or short label (e.g., do not write just 'plan_trip').
- **Merge Context:** Read the `[SYSTEM STATE]` block and merge relevant historical details (places, dates, constraints already given) with the current message.
- **Be Comprehensive:** Preserve every concrete detail (quantities, specific requests) in full sentences. If you write something short enough to fit a chat title, you have dropped information the planner needs.

### If action = `answer_directly`
- **Target Field:** Write ONLY in the `text` field.
- **Active Conversation:** Treat the `[SYSTEM STATE]` Recent conversation as the actual, ongoing conversation you are having. Respond as its next turn, not as a fresh opening message.
- **Engage the Thread:** If the user is mid-joke, mid-explanation, or referencing something said earlier, your reply must engage with that specific thread. Acknowledge what they told you instead of falling back to a generic greeting or restarting the exchange.
- **Play Along:** If the user initiates a joke, game, banter, or conversational script (like a "knock-knock" joke), play your expected role naturally (e.g., respond "Who's there?"). DO NOT explain the joke, do not analyze the interaction, and do not act like an AI observing the conversation from the outside. Just play along."""


def build_routing_decision_system_message() -> str:
    """The full system message for the Phase-2 structured routing decision."""
    return ROUTING_DECISION_SYSTEM_MESSAGE


def build_routing_decision_prompt(system_state: str, query: str, gathered_context: str = "") -> str:
    """The human-turn prompt for the Phase-2 structured routing decision —
    the [SYSTEM STATE] block (if any), the raw user message, and anything
    Phase 1's tool-calling already gathered this turn."""
    prompt = f"{system_state}\n\nUser message: {query!r}" if system_state else f"User message: {query!r}"
    if gathered_context:
        prompt += f"\n\nContext you already gathered this turn: {gathered_context}"
    return prompt


# ── Result synthesis (after a workflow finishes) ────────────────────────


def build_synthesis_prompt(plan: dict, results_count: int, artifacts_paths: list[str]) -> str:
    """Prompt asking the LLM to turn a completed workflow's raw results
    into a user-facing summary, including any generated artifacts' links."""
    synthesis_query = (
        f"Synthesize the following workflow results:\n"
        f"Plan: {json.dumps(plan, indent=2)}\n"
        f"Results count: {results_count}\n"
    )
    if artifacts_paths:
        synthesis_query += "Generated artifacts:\n" + "\n".join(f"  - {p}" for p in artifacts_paths) + "\n"
    synthesis_query += "Include download links for any generated files in your response."
    return synthesis_query
