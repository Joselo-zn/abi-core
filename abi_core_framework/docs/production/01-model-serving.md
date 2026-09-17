# Model Serving

Two strategies for running AI models. Choose when you create the project.

## Centralized (recommended)

One shared Ollama instance serves all agents. Less RAM, easier to manage.

```bash
abi-core create project my-app --model-serving centralized
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
abi-core create project my-app --model-serving distributed
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

If your agent uses OpenAI, Gemini, or another cloud provider, it doesn't need Ollama at all:

```python
# config.py
LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": os.getenv("OPENAI_API_KEY"),
}
```

You can mix: some agents use local Ollama, others use cloud APIs. Each agent has its own `LLM_CONFIG`.

### Temperature and provider-specific parameters

`temperature` is optional — omit it (the default) to let the provider pick its own value. This matters most for Claude: **as of Claude 4.7 and later (and Claude Mythos Preview), Anthropic's API no longer supports `temperature`, `top_p`, or `top_k` at all** — any non-default value returns an HTTP 400, unconditionally, not just with extended `thinking` enabled ([Anthropic docs](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)). Don't set `LLM_TEMPERATURE`/`"temperature"` for those models — there's no "safe" value to fall back to. Set it explicitly only for providers/models that still honor it.

For anything else provider- or model-generation-specific — Claude's `thinking`, Gemini's `thinking_budget` (2.5) or `thinking_level` (3+), Azure's required `api_version`, `max_tokens`, `top_p`, etc. — use `extra_params`, forwarded as-is to the underlying model constructor:

```python
LLM_CONFIG = {
    "provider": "anthropic",
    "model": "claude-opus-4-6-20260115",
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    "extra_params": {
        "thinking": {"type": "enabled", "budget_tokens": 4000},
        "max_tokens": 8000,
    },
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
