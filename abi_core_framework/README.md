# ABI-Core

[![PyPI version](https://badge.fury.io/py/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![Python](https://img.shields.io/pypi/pyversions/abi-core-ai.svg)](https://pypi.org/project/abi-core-ai/)
[![License](https://img.shields.io/pypi/l/abi-core-ai.svg)](https://github.com/Joselo-zn/abi-core/blob/main/LICENSE)
[![Documentation](https://readthedocs.org/projects/abi-core/badge/?version=latest)](https://abi-core.readthedocs.io/en/latest/?badge=latest)

**AI agents that work together — and keep working on Monday.**

You've seen the demo. The agent books the flight, writes the code, answers the customer — on stage, in ninety seconds. Then it meets real users, and it invents a refund policy, resets the wrong password, and bills the same order twice. Not because the model is dumb. Because nobody decided where the model stops.

I'm ABI. You write plain Python. The model thinks inside steps you control; your code decides what happens, in what order, and what's allowed. Agents run in their own containers, find each other by what they can do, ask a policy engine before they act, and wait for a person when it matters. Local model by default. Any provider when you want one.

👉 [Why ABI-Core](https://abi-core.readthedocs.io/en/latest/why-abi-core.html) — the opinions behind all of this, and the one thing I saved for last.

> **Beta.** The framework works end to end; APIs may still change between minor versions. Pin your version.

---

## Quick start

You need Python 3.11+ and Docker.

```bash
pip install abi-core-ai

abi-core create project --name my-system      # answer "n" to the semantic layer and Guardian for now
cd my-system
abi-core add agent --name assistant --description "Answers questions" --with-web-interface
                                               # tasks/skills: answer
```

Make the agent answer — replace `agents/assistant/steps.py` with:

```python
from app import agent
from config import config
from abi_core.agent.llm_provider import invoke


@agent.step(name="answer_step", input_map={"query": "$input.query"})
async def answer_step(query):
    return {"answer": await invoke(config.LLM_CONFIG, query)}
```

Pull a model, start everything, and talk to it:

```bash
docker volume create ollama_data              # once per machine; `abi-core run` also creates it
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build

curl -N -X POST http://localhost:8002/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "In one sentence: what is an AI agent?"}'
```

Want a chat window instead of `curl`? `abi-core add chainlit`, then `abi-core run`, and open http://localhost:8500.

👉 [Your First Project](https://abi-core.readthedocs.io/en/latest/getting-started/04-first-project.html) walks through it step by step.

---

## The idea: the AI thinks, your code decides

```python
@agent.step(name="classify")
async def classify(message):
    raw = await invoke(config.LLM_CONFIG, f"Reply with one word — faq, order or human: {message}")
    intent = raw.strip().lower()
    return {"intent": intent if intent in {"faq", "order", "human"} else "other"}   # code has the last word
```

The model reads the message. Code decides what its answer is allowed to be — and everything after it.

- **Steps and tasks.** `@agent.step` functions each do one thing; an `@agent.task` composes them in plain Python — sequences, branches, `asyncio.gather` for parallel work. The model never reorders them.
- **Output with a fixed shape.** `invoke_structured(config, prompt, MyPydanticModel)` makes the model fill a schema, enforced while it generates.
- **Fast decisions, with a confidence.** `invoke_classifier(state, questions)` asks a decision model (Laya on Ollama) to pick between options: no text generated, a probability for each option, a fraction of a second on CPU. Act when it's sure; ask the chat model when it isn't. See [Fast Classification](https://abi-core.readthedocs.io/en/latest/single-agent/12-fast-classification.html).
- **Rules outside the model.** Guardian and OPA evaluate your policies before an action runs. A prompt can be talked around; a policy file can't.
- **A person approves what matters.** Plan confirmation shows a plan (or a draft, or an order) and waits for approve / modify / reject — in any language, or with buttons in the chat.
- **Memory and sessions.** Session-scoped context, short- and long-term memory, Redis when you run more than one replica.
- **Agents find each other.** The Semantic Layer lets an agent ask "who can analyze revenue?" instead of hard-coding an address.
- **Work in the background.** `@agent.task_async` with retries and status, `@agent.task_schedule` for recurring jobs.
- **Run generated code safely.** A throwaway sandbox: no network, no credentials, hard limits.
- **A chat UI that shows its work.** Chainlit with live progress, review cards and Google login.

---

## Use cases you can build in under an hour

Each one is a working proof of concept with every file on the page, tested against a local model:

| Use case | What the model does | What code decides |
|---|---|---|
| [Customer Support & Triage](https://abi-core.readthedocs.io/en/latest/use-cases/01-customer-support.html) | Understands the question, writes the reply | Which help-center entry, order lookups, refusing to guess, escalation |
| [Clinical Documentation](https://abi-core.readthedocs.io/en/latest/use-cases/02-clinical-scribing.html) | Turns a visit transcript into a note | The note's schema, drugs checked against the transcript, clinician sign-off |
| [Lead Qualification](https://abi-core.readthedocs.io/en/latest/use-cases/03-lead-qualification.html) | Reads the lead's email, drafts outreach | The score, every point explained; nothing is sent without approval |
| [Natural-Language Data Access](https://abi-core.readthedocs.io/en/latest/use-cases/04-nl-data-access.html) | Turns a question into SQL | Read-only access, date ranges, row and time limits |
| [IT Help Desk](https://abi-core.readthedocs.io/en/latest/use-cases/05-it-help-desk.html) | Understands the request | Who may reset what, decided by an OPA policy |
| [Workflow Automation](https://abi-core.readthedocs.io/en/latest/use-cases/06-workflow-automation.html) | Reads the order email | Parallel checks, prices, billing once, background retries |
| [Supply Chain](https://abi-core.readthedocs.io/en/latest/use-cases/07-supply-chain.html) | Explains the plan | The forecast, reorder points and quantities |
| [Deep Research](https://abi-core.readthedocs.io/en/latest/use-cases/08-deep-research.html) | Takes notes, writes the report | Every quote checked word for word, every citation checked |

---

## Any model

A generated agent reads its model from the environment — switching provider is a change in `compose.yaml`, not in code:

```yaml
environment:
  - LLM_PROVIDER=anthropic          # ollama (default), openai, anthropic, gemini, grok, bedrock, azure, vertex
  - MODEL_NAME=claude-opus-5-5
  - LLM_API_KEY=${ANTHROPIC_API_KEY}
  - 'LLM_EXTRA_PARAMS={"thinking": {"type": "adaptive"}}'   # anything provider-specific, passed as-is
```

Install the provider's extra in the agent: `abi-core-ai[anthropic]`, `[openai]`, `[gemini]`, `[grok]`, `[bedrock]`, `[vertex]` — or `[providers]` for all of them. See [Model Serving](https://abi-core.readthedocs.io/en/latest/production/01-model-serving.html).

---

## The CLI

```bash
abi-core create project --name <name> [--with-semantic-layer] [--with-guardian]
abi-core add agent --name <name> --description "..." [--with-web-interface]
abi-core add service semantic-layer | mcp-api | agent-memory
abi-core add chainlit                 # chat UI as a Docker service
abi-core add policies --name <name>   # starter OPA policy (needs Guardian)
abi-core run [--build] [--logs]
```

Full reference: [CLI Reference](https://abi-core.readthedocs.io/en/latest/reference/cli-reference.html).

---

## Reference agents

`abi_agents` ships the Orchestrator, Planner and Builder — the pieces behind ABI Swarm, which turns one request into a plan, waits for your approval, and creates the agents it's missing. They're alpha, and not scaffolded by a single command: use them as a reference and wire each one into your project. See [Planner & Orchestrator](https://abi-core.readthedocs.io/en/latest/orchestration/01-planner-orchestrator.html).

---

## Links

- **Documentation:** https://abi-core.readthedocs.io
- **Examples:** https://github.com/Joselo-zn/abi-core-examples
- **Source and issues:** https://github.com/Joselo-zn/abi-core
- **Changelog:** https://abi-core.readthedocs.io/en/latest/changelog.html

## Contributing

```bash
git clone https://github.com/Joselo-zn/abi-core
cd abi-core/abi_core_framework
uv sync --dev
uv run pytest
```

## License

Apache 2.0 — see [LICENSE](https://github.com/Joselo-zn/abi-core/blob/main/LICENSE).

---

**Built by [José Luis Martínez](https://github.com/Joselo-zn).**
