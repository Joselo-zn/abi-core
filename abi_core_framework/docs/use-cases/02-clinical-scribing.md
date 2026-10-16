# Clinical Documentation & Scribing

```{warning}
This is a proof of concept, not a medical device. Don't use it with real patients or real patient data. The transcript on this page is invented.
```

Many agentic systems are built to sound sure of themselves. In a clinic that's the worst thing they can be. Hand one a visit transcript and it writes a note that reads beautifully — and quietly fills the gaps the doctor left. An illustration, not any real product's output:

```
Transcript: "...I'll prescribe the usual antibiotic for three days."

Draft note:
  Medications: Nitrofurantoin 100 mg twice daily for 3 days
  Allergies:   None known
  Plan:        Urine culture ordered.
```

Nobody named the drug. Nobody asked about allergies. Nobody ordered a culture. But the note looks finished, the doctor is on patient number twenty-three, and "Approve" is one click away.

I'm ABI, and I keep the two jobs apart. Reading a messy conversation and writing clinical prose is non-deterministic work, so the model does it. Everything that has to be exact is code: the shape of the note is fixed by a schema, every drug and allergy is checked against what was actually said, and nothing is saved until the clinician approves it. Here's an excerpt from a real run with the transcript below:

```
Medications:
- lisinopril 10 mg — Every morning
- ibuprofen 400 mg — Every 8 hours with food, for up to five days
Allergies: sulfa drugs
Follow-up: Return if not better in a week or if unable to swallow liquids.

Approve the note, reject it, or tell me what to change.

Clinician: Change the follow-up to: come back in 3 days if the fever doesn't go down.

Follow-up: Come back in 3 days if the fever doesn't go down.

Clinician: Looks good, approve it.

✅ Approved by the clinician · 2026-10-12 00:30 UTC
```

And with the "usual antibiotic" transcript, in three runs out of three, the model left the medication list empty instead of naming a drug nobody said.

It takes about twenty-five minutes to build.

## What you'll build

One agent, `scribe`, that works in two turns:

```
transcript ──▶ model fills the note (shape forced by a schema)
           ──▶ code: was every drug and allergy actually said?
           ──▶ draft shown to the clinician, with any doubts flagged
                 │
                 ├─ approve ──▶ code stamps it as signed (→ your EHR)
                 ├─ change  ──▶ model applies only that change ──▶ checked again ──▶ shown again
                 └─ reject  ──▶ nothing is saved
```

ABI features on this page: `invoke_structured` (output forced into a Pydantic schema), the [plan confirmation](../single-agent/09-plan-confirmation.md) building block reused as a clinician sign-off, [session memory](../single-agent/04-agents-with-memory.md), and the Chainlit approve/modify/reject buttons.

## Step 1: Create the project and the agent

```bash
abi-core create project --name clinic
cd clinic
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name scribe \
  --description "Turns a visit transcript into a structured clinical note for the clinician to approve" \
  --with-web-interface
```

When it asks for tasks/skills, type `scribe`. Press Enter for the URL.

## Step 2: The shape of the note

This is the contract. The model can only fill these fields — it can't add a section, skip one, or return free text. `invoke_structured` enforces it while the model generates, not after.

Replace the contents of `agents/scribe/models.py`:

```python
"""The shape of a clinical note. The model must fill exactly this — nothing more."""

from typing import List

from pydantic import BaseModel, Field


class Medication(BaseModel):
    name: str = Field(description="Drug name exactly as said in the visit")
    dose: str = Field(description="Dose as said, e.g. '400 mg'; empty if not said")
    instructions: str = Field(description="How and how long to take it; empty if not said")


class ClinicalNote(BaseModel):
    chief_complaint: str = Field(description="Why the patient came, in one line")
    subjective: str = Field(description="What the patient reports: symptoms, history, timeline")
    objective: str = Field(description="What the clinician observed or measured; empty if nothing was")
    assessment: str = Field(description="The clinician's working diagnosis, as stated in the visit")
    plan: str = Field(description="Tests, treatment and advice the clinician gave")
    medications: List[Medication] = Field(description="Every medication prescribed or changed in this visit")
    allergies: List[str] = Field(description="Allergies mentioned in the visit")
    follow_up: str = Field(description="When and why to come back; empty if not said")
```

## Step 3: The prompts

Create `agents/scribe/prompts.py`:

```python
EXTRACT_PROMPT = """You are a clinical scribe. Turn this visit transcript into a structured note.

Rules:
- Use only what was said in the transcript. Never add a diagnosis, drug, dose or test that wasn't said.
- If something wasn't said, leave that field empty.
- Write in plain, neutral clinical language.

Transcript:
{transcript}"""

REVISE_PROMPT = """You are a clinical scribe. The clinician reviewed your draft note and asked for a change.
Apply exactly that change and keep everything else as it is.
Never add anything that isn't in the transcript or in the clinician's request.

Transcript:
{transcript}

Current draft (JSON):
{note}

Clinician's request:
{feedback}"""
```

## Step 4: The steps

Two steps ask the model: write the note, revise the note. The other three are plain code — and they're the ones that make it safe.

Replace the contents of `agents/scribe/steps.py`:

```python
import json
from datetime import datetime, timezone

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke_structured
from models import ClinicalNote
from prompts import EXTRACT_PROMPT, REVISE_PROMPT


@agent.step(name="extract_note")
async def extract_note(transcript):
    """The model fills the note. The schema decides its shape — not the model."""
    note = await invoke_structured(
        config.LLM_CONFIG, EXTRACT_PROMPT.format(transcript=transcript), ClinicalNote
    )
    return {"note": note.model_dump()}


@agent.step(name="revise_note")
async def revise_note(note, feedback, transcript):
    revised = await invoke_structured(
        config.LLM_CONFIG,
        REVISE_PROMPT.format(transcript=transcript, note=json.dumps(note, indent=2), feedback=feedback),
        ClinicalNote,
    )
    return {"note": revised.model_dump()}


@agent.step(name="check_against_transcript")
async def check_against_transcript(note, transcript, feedback=""):
    """Every drug and allergy in the note must have been said — in the visit
    or in the clinician's own correction. Plain string matching, no model."""
    said = f"{transcript}\n{feedback}".lower()
    names = [m["name"] for m in note["medications"]] + note["allergies"]
    return {"unverified": [n for n in names if n.strip() and n.lower() not in said]}


@agent.step(name="render_note")
async def render_note(note, unverified=None, signed_at=None):
    """Turn the note into readable text. Deterministic: same note, same text."""
    meds = "\n".join(
        f"- {m['name']} {m['dose']} — {m['instructions']}".replace("  ", " ").rstrip(" —")
        for m in note["medications"]
    ) or "- None"
    lines = [
        f"**Chief complaint:** {note['chief_complaint']}",
        f"**Subjective:** {note['subjective']}",
        f"**Objective:** {note['objective'] or '—'}",
        f"**Assessment:** {note['assessment']}",
        f"**Plan:** {note['plan']}",
        f"**Medications:**\n{meds}",
        f"**Allergies:** {', '.join(note['allergies']) or 'None mentioned'}",
        f"**Follow-up:** {note['follow_up'] or '—'}",
    ]
    if unverified:
        lines.append(
            "⚠️ **Check before approving** — not found in the transcript: " + ", ".join(unverified)
        )
    if signed_at:
        lines.append(f"✅ **Approved by the clinician** · {signed_at}")
    return {"text": "\n\n".join(lines)}


@agent.step(name="sign_note")
async def sign_note(note):
    """Stamp the approval. In production, this is where the note goes to your EHR."""
    return {"signed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
```

`check_against_transcript` is deliberately simple: a drug or allergy that doesn't appear, word for word, in the transcript or in the clinician's correction gets flagged. It can flag something harmless — a brand name for a generic the doctor said — and that's the right way to be wrong: the clinician looks twice.

## Step 5: The task

Approving a note is the same problem as approving a plan: something is proposed, it waits, and a person says yes, no, or "change this". ABI already has that building block, so the task reuses it — including understanding replies in plain language, in any language.

Replace the contents of `agents/scribe/tasks.py`:

```python
from app import agent
from config import config
from abi_core.agent.agent_response import AgentResponse
from abi_core.agent.plan_confirmation import (
    classify_plan_confirmation_reply,
    clear_pending_plan,
    record_pending_plan,
)

SIGNED_NOTES = []  # In production: send the signed note to your EHR instead.

REVIEW_HINT = "\n\n---\nApprove the note, reject it, or tell me what to change."


@agent.task(name="scribe", task_id="task-scribe")
async def scribe(query, context_id=None):
    session = await agent.get_session_context(context_id)
    draft = session.get("pending_plan")  # the note waiting for the clinician, if any

    # 1. Is this a new transcript, or the clinician answering about a draft?
    reply = await classify_plan_confirmation_reply(
        query, session, config.LLM_CONFIG, session_id=context_id
    )
    decision = reply["classification"] if reply else "new_transcript"

    if decision == "new_transcript":
        yield AgentResponse.status("Reading the transcript...")
        note = (await agent.execute_step("extract_note", transcript=query))["note"]
        async for response in _propose(note, query, context_id):
            yield response

    elif decision == "plan_confirmed":
        note = draft["note"]
        signed_at = (await agent.execute_step("sign_note", note=note))["signed_at"]
        SIGNED_NOTES.append({"context_id": context_id, "note": note, "signed_at": signed_at})
        await clear_pending_plan(agent.update_session_context, context_id)
        text = (await agent.execute_step("render_note", note=note, signed_at=signed_at))["text"]
        yield AgentResponse.text(text)

    elif decision == "plan_rejected":
        await clear_pending_plan(agent.update_session_context, context_id)
        yield AgentResponse.text("Draft discarded. Nothing was saved.")

    elif decision == "plan_modify_requested":
        await agent.update_session_context(context_id, {"awaiting_plan_modification": True})
        yield AgentResponse.input_required("What should change in the note?")

    elif decision == "plan_modify_feedback":
        yield AgentResponse.status("Updating the note...")
        transcript = reply["original_query"]
        note = (await agent.execute_step(
            "revise_note", note=draft["note"], feedback=reply["feedback"], transcript=transcript
        ))["note"]
        async for response in _propose(note, transcript, context_id, feedback=reply["feedback"]):
            yield response

    else:  # plan_confirmation_orphaned: a button press with no draft waiting
        yield AgentResponse.text("There's no draft waiting for review. Paste a visit transcript to start.")


async def _propose(note, transcript, context_id, feedback=""):
    """Check the draft against what was said, park it, and ask the clinician."""
    unverified = (await agent.execute_step(
        "check_against_transcript", note=note, transcript=transcript, feedback=feedback
    ))["unverified"]
    await record_pending_plan(agent.update_session_context, context_id, {"note": note}, transcript)
    text = (await agent.execute_step("render_note", note=note, unverified=unverified))["text"]
    yield AgentResponse.input_required(text + REVIEW_HINT, action_type="plan_confirmation")
```

## Step 6: Run it

Turn off qwen3's think-out-loud mode for this agent — in `compose.yaml`, add to the `environment` of the `clinic-scribe` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Add the chat window, pull the model and start everything:

```bash
abi-core add chainlit
docker volume create ollama_data              # once per machine; `abi-core run` also creates it
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 7: Use it

Open **http://localhost:8500** and paste a visit transcript — the one in the script below works. The draft comes back with three buttons under it: approve, modify, reject. Press modify and type the change, or just write it ("make the follow-up three days"). Each chat in the window is one visit.

### Or from a script

To replay the same visit after every change, use [`AgentStreamClient`](../single-agent/05-testing-agents.md#talk-to-it-from-python). Save this as `visit.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

TRANSCRIPT = """Doctor: Good morning, what brings you in today?
Patient: I've had a sore throat and a fever for three days. It hurts to swallow.
Doctor: Any cough or runny nose?
Patient: A little cough, no runny nose.
Doctor: Any allergies to medications?
Patient: Yes, I'm allergic to sulfa drugs.
Doctor: Are you taking anything right now?
Patient: Just lisinopril, 10 mg every morning, for my blood pressure.
Doctor: Your temperature is 38.4 and your tonsils are red and swollen, no white patches.
Doctor: This looks like a viral pharyngitis. Antibiotics won't help here.
Doctor: Take ibuprofen 400 mg every 8 hours with food for the pain and fever, for up to five days.
Doctor: Drink plenty of fluids and rest. Keep taking your lisinopril as usual.
Doctor: If you're not better in a week, or you can't swallow liquids, come back."""

MESSAGES = [
    TRANSCRIPT,
    "Change the follow-up to: come back in 3 days if the fever doesn't go down.",
    "Looks good, approve it.",
]

async def main():
    client = AgentStreamClient("http://localhost:8002")  # one client = one visit
    for m in MESSAGES:
        print(f"\n>>> {m[:70]}{'...' if len(m) > 70 else ''}")
        async for e in client.stream(m):
            if e.get("is_task_completed") or e.get("require_user_input") or e.get("response_type") == "error":
                print(e.get("content"))


asyncio.run(main())
```

```bash
python visit.py
```

On a laptop CPU with `qwen3:latest`, the draft took about a minute, the revision a little more, and the approval two seconds.

## What happened

1. **The transcript arrived.** Nothing was pending, so the task treated it as a new visit. The model filled `ClinicalNote` — it had no way to return anything else.
2. **Code checked the draft.** `lisinopril`, `ibuprofen` and `sulfa drugs` all appear in the transcript, so nothing was flagged. The draft was parked in the session and shown with the buttons.
3. **"Change the follow-up..."** The plan-confirmation classifier recognized a change request and extracted the change. The model rewrote only the follow-up; code checked the result again.
4. **"Looks good, approve it."** Recognized as an approval. Code stamped the note as signed and cleared the draft. That stamp is the only way a note gets saved.

What the model never did: decide the note was finished, skip the check, or save anything.

## Before you put it near a clinic

- **Use a real transcription step.** Speech-to-text runs before this agent; the agent starts at text, which keeps the two problems apart.
- **Send signed notes to your EHR.** Replace `SIGNED_NOTES` with your EHR's API, and record who approved each note — the clinician's identity, not just the time. The [Chainlit login](../production/07-authentication.md) gives you that identity.
- **Match your note format.** `ClinicalNote` is a generic SOAP note. Change the schema to your specialty's template; the code that checks and renders it follows.
- **Make the check stricter, not looser.** Add doses, or a list of drugs your service never prescribes without a second look.
- **Handle patient data under the rules that apply to you** (for example HIPAA or GDPR). Keep the model local, as on this page, or use a provider your organization has approved for clinical data.
- **Keep sessions safe.** Set `SESSION_BACKEND=redis` so a draft survives restarts — see [Sessions & Multi-turn](../single-agent/07-sessions-multi-turn.md).

## Next

👉 Back to [Use Cases](index.md)
