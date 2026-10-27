# Fast Classification with a Decision Model

```{note}
**New.** `invoke_classifier` needs Ollama 0.40 or later.
```

A lot of what an agent decides is a choice between a few known options: is this message about an order, a general question, or a request for a person? Did the user approve the plan, reject it, or ask for changes? You can ask a chat model with `invoke_structured` — it works, but it generates text to answer, it takes seconds, and it tells you its answer without telling you how sure it is.

A **decision model** answers that kind of question differently. It doesn't write anything: it scores every option in a single pass and returns a probability for each one. On CPU that takes a fraction of a second, and the probabilities are what let your code decide what to do when the model isn't sure.

`invoke_classifier` calls one. ABI's default is [Laya](https://ollama.com/library/laya), served by Ollama.

## Set it up

```bash
docker exec ollama ollama --version       # 0.40 or later
docker exec ollama ollama pull laya       # the English model, about 850 MB
```

`invoke_classifier` asks for the model named `laya` unless told otherwise. If you pull a specific tag — `laya:421m-english-bf16`, say — set `CLASSIFIER_MODEL` to that tag: pulling a tag doesn't create the `laya` name.

| Variable | Default | |
|---|---|---|
| `CLASSIFIER_MODEL` | `laya` | The decision model |
| `CLASSIFIER_BASE_URL` | `OLLAMA_HOST`, then `http://localhost:11434` | The Ollama that serves it |

The `model=` and `base_url=` arguments override both.

## Ask questions about a state

You describe the situation in `state` and ask one or more `questions` about it. Each question has a `type`, `instructions` and `criteria` — one entry per possible answer, each with a sentence saying what it means.

```python
from abi_core.agent import invoke_classifier

answers = await invoke_classifier(
    state="Customer message: Where is my order 10045? It was supposed to arrive yesterday!",
    questions={
        "intent": {
            "type": "choice",
            "instructions": "What does the customer want?",
            "criteria": {
                "faq": "A general question about shipping, returns or payments.",
                "order": "Something about one of their orders.",
                "human": "To talk to a person.",
                "chitchat": "Greeting, thanks or small talk.",
            },
        },
        "upset": {
            "type": "noul",
            "instructions": "Is the customer upset?",
            "criteria": {"true": "Upset, frustrated or angry.", "false": "Calm."},
        },
    },
)
```

Both questions are answered in the same call. The answers come back keyed by question name, as the model returns them:

```python
answers["intent"]["choice"]          # "order"
answers["intent"]["confidence"]      # 0.94
answers["intent"]["probabilities"]   # {"faq": 0.02, "order": 0.96, "human": 0.01, "chitchat": 0.01}
answers["upset"]["noul"]             # 0.69 — the probability of "true"
```

| `type` | Asks | Answer fields |
|---|---|---|
| `choice` | Which one of 2 to 26 options | `choice`, `probabilities`, `confidence` |
| `noul` | True or false | `noul`: the probability of true |
| `score` | Where it falls on a scale of 2 to 10 levels | `score`, `legend`, `probabilities`, `confidence` |

Up to 64 questions per call.

### Scores

A `score` question rates the state on an ordered scale. Its `criteria` is a **list** of levels, lowest first — not a dict like the other two:

```python
answers = await invoke_classifier(
    state="Customer message: My card was charged twice for order 10045, fix it now.",
    questions={
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this message?",
            "criteria": ["Can wait days.", "Today would be nice.", "Needs an answer now."],
        },
    },
)
answers["urgency"]["score"]          # 1.81 — the expected level, counting from 0
answers["urgency"]["legend"]         # {"0": "Can wait days.", "1": "Today would be nice.", "2": "Needs an answer now."}
answers["urgency"]["probabilities"]  # {"0": 0.02, "1": 0.16, "2": 0.83}
answers["urgency"]["confidence"]     # 0.71
```

`score` is a number between the lowest level (0) and the highest, not one of the levels: 1.81 means "mostly *needs an answer now*". Round it, or compare it with a threshold, in your code.

## Read the confidence, not just the answer

These are real answers from Laya on CPU, about 0.3 seconds each for both questions:

| Customer message | `choice` | `confidence` | `upset` |
|---|---|---|---|
| "Where is my order 10045? It was supposed to arrive yesterday!" | order | 0.94 | 0.69 |
| "This is useless, let me talk to a real person NOW." | human | 0.91 | 0.82 |
| "Thanks, that's all." | chitchat | 0.23 | 0.30 |
| "Do you ship to Canada?" | faq | 0.11 | 0.25 |

All four choices are right. But the last two came with low confidence, and a classifier that's right without being sure is one you shouldn't follow blindly. What counts as "sure enough", and what to do below it, is your decision — `invoke_classifier` only reports. A common pattern: take the classifier's answer when it's confident, and ask the chat model only when it isn't.

```python
from pydantic import BaseModel
from typing import Literal

from app import agent
from config import config
from abi_core.agent import invoke_classifier, ClassifierError
from abi_core.agent.llm_provider import invoke_structured

INTENTS = {
    "faq": "A general question about shipping, returns or payments.",
    "order": "Something about one of their orders.",
    "human": "To talk to a person.",
    "chitchat": "Greeting, thanks or small talk.",
}
SURE_ENOUGH = 0.5


class Intent(BaseModel):
    intent: Literal["faq", "order", "human", "chitchat"]


@agent.step(name="classify", input_map={"message": "$input.query"})
async def classify(message):
    try:
        answers = await invoke_classifier(
            state=f"Customer message: {message}",
            questions={"intent": {"type": "choice",
                                  "instructions": "What does the customer want?",
                                  "criteria": INTENTS}},
        )
        confidence = answers["intent"]["confidence"]
    except ClassifierError:
        confidence = 0                                      # no classifier: treat as unsure
    if confidence >= SURE_ENOUGH:
        return {"intent": answers["intent"]["choice"], "decided_by": "classifier"}

    # Not sure: ask the chat model, with the options spelled out.
    options = "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
    decision = await invoke_structured(
        config.LLM_CONFIG,
        f"Classify the customer's message.\n{options}\n\nMessage: {message}",
        Intent,
    )
    return {"intent": decision.intent, "decided_by": "llm"}
```

Run against the four messages above, the classifier settled the first two in 0.24 s each and passed the other two to the chat model; with no classifier reachable, all four went to the chat model, at 1.5 to 2 seconds each (qwen3 on the same CPU). The fast path answers the clear cases; the slow path is there for the rest. Return `decided_by` and you can count how often each one runs.

## When it fails

- **`ValueError`**, before any call, when the request is malformed: an empty `state`, no questions, more than 64, an unknown `type`, or `criteria` of the wrong shape (a `choice` with fewer than 2 or more than 26 options, a `score` that isn't a list of 2 to 10 levels). That's a bug in your code — let it surface.
- **`ClassifierError`** when the model can't answer: Ollama is unreachable or times out (`timeout=`, 60 s by default), the model rejects the request — for instance, `qwen3:latest is not a llama.cpp decision model` if `CLASSIFIER_MODEL` points at a chat model — or the answer comes back incomplete.

Treat `ClassifierError` as confidence 0, like the example above: your agent keeps working without the classifier, only slower.

## Good to know

- **Write criteria as sentences.** The model scores each option by its description, not its key: `"order": "Something about one of their orders."` works better than `"order": "order"`.
- **Put what matters in `state`.** It's all the model sees. Label it (`Customer message: …`, `Plan: … / Reply: …`) when there's more than one piece.
- **English.** `laya` is the English model. A multilingual variant exists (`laya:322m-multilingual-bf16`); measure it on your own messages before relying on it.
- **Not a chat model.** It can't write a reply, extract a value or follow instructions — only choose. Use `invoke` or `invoke_structured` for those.

## Next step

👉 [Testing Agents](05-testing-agents.md)
