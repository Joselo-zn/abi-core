# Model Serving

Two strategies for running AI models. Choose when you create the project.

## Centralized (recommended)

One shared Ollama instance serves all agents. Less RAM, easier to manage.

```bash
abi-core create project --name my-app --model-serving centralized
```

```
┌─────────────┐
│   Ollama    │ ← All agents connect here
└─────────────┘
      ↑
  Agent 1, Agent 2, Agent 3
```

Agents point to the same `OLLAMA_HOST`:
```yaml
environment:
  - OLLAMA_HOST=http://my-app-ollama:11434
  - START_OLLAMA=false
```

## Distributed

Each agent runs its own Ollama. Full isolation, independent model versions.

```bash
abi-core create project --name my-app --model-serving distributed
```

```
Agent 1 ← Ollama 1 (qwen3:latest)
Agent 2 ← Ollama 2 (llama3:8b)
Agent 3 ← Ollama 3 (mistral:7b)
```

Agents manage their own Ollama:
```yaml
environment:
  - OLLAMA_HOST=http://localhost:11434
  - START_OLLAMA=true
  - LOAD_MODELS=true
```

## Cloud providers (no Ollama needed)

If your agent uses OpenAI, Gemini, Claude or another cloud provider, it doesn't need Ollama at all. A generated agent builds its model config from the environment (`LLM_CONFIG = llm_config_from_env(...)` in `config/config.py`), so switching provider is a change in `compose.yaml` or `.env`, not in code:

```yaml
services:
  my-app-analyst:
    environment:
      - LLM_PROVIDER=anthropic
      - MODEL_NAME=claude-opus-5-5
      - LLM_API_KEY=${ANTHROPIC_API_KEY}
```

Install the provider's extra in the agent's `requirements.txt` (`abi-core-ai[anthropic]`, `[openai]`, `[gemini]`, ...). A hosted provider never receives your Ollama URL: `OLLAMA_HOST` is only used when the provider is `ollama`, and `LLM_BASE_URL` only when you set it.

You can mix: some agents use local Ollama, others use cloud APIs. Each agent reads its own environment.

### Temperature

`temperature` is optional — leave `LLM_TEMPERATURE` unset and the provider picks its own value. This matters most for Claude: Claude Opus 4.7 and newer and Claude Sonnet 5 and newer reject `temperature`, `top_p` and `top_k` with an HTTP 400 (Claude Sonnet 5.5 rejects any non-default value). Older models such as Claude Opus 4.6, Sonnet 4.6 and Haiku 4.5 still accept them. Set `LLM_TEMPERATURE` only where the provider and model still honor it.

### Provider-specific parameters

For anything provider- or model-specific — Claude's `thinking`, Gemini's `thinking_budget` (2.5) or `thinking_level` (3+), Azure's required `api_version`, `max_tokens` — set `LLM_EXTRA_PARAMS` to a JSON object. It is passed as-is to the LangChain model:

```yaml
    environment:
      - LLM_PROVIDER=anthropic
      - MODEL_NAME=claude-opus-5-5
      - LLM_API_KEY=${ANTHROPIC_API_KEY}
      - 'LLM_EXTRA_PARAMS={"thinking": {"type": "adaptive"}, "max_tokens": 16000}'
```

- On current Claude models a fixed thinking budget (`{"type": "enabled", "budget_tokens": N}`) is rejected with an HTTP 400 — use `{"type": "adaptive"}`.
- `LLM_EXTRA_PARAMS` goes on top of the agent's own defaults. With Ollama, the reference Orchestrator and the ephemeral agents turn qwen3's thinking mode off (`{"reasoning": false}`); `{"reasoning": true}` turns it back on.
- Invalid JSON, or JSON that isn't an object, stops the agent at start-up with an error naming the variable. An empty value counts as unset.
- Ephemeral agents have their own `EPHEMERAL_LLM_EXTRA_PARAMS`, set on the Builder — see [Environment Variables](../reference/environment-variables.md).

### Writing the config by hand

An agent you write yourself can still build the dict directly — `extra_params` is the same object `LLM_EXTRA_PARAMS` fills in:

```python
LLM_CONFIG = {
    "provider": "anthropic",
    "model": "claude-opus-5-5",
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    "extra_params": {"thinking": {"type": "adaptive"}, "max_tokens": 16000},
}
```

## Switch strategy

Edit `.abi/runtime.yaml`:

```yaml
project:
  model_serving: centralized  # or distributed
```

Then rebuild: `docker compose up --build -d`

## Next step

👉 [Monitoring & Logs](02-monitoring-logs.md)
