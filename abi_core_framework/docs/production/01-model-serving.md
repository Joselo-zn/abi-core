# Model Serving

Two strategies for running LLMs. Choose when you create the project.

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
Agent 1 ← Ollama 1 (qwen2.5:3b)
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

## Switch strategy

Edit `.abi/runtime.yaml`:

```yaml
project:
  model_serving: centralized  # or distributed
```

Then rebuild: `docker compose up --build -d`

## Next step

👉 [Monitoring & Logs](02-monitoring-logs.md)
