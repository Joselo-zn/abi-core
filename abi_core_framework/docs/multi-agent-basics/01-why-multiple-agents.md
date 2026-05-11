# Why Multiple Agents?

One agent that does everything gives generic answers. Multiple specialized agents give expert answers.

## The problem

```
One agent doing everything:
  "Analyze sales" → mediocre
  "Write a report" → mediocre
  "Translate to Spanish" → mediocre
```

## The solution

```
Specialized agents:
  Analyst → expert at analysis
  Writer → expert at reports
  Translator → expert at languages
```

Each agent has its own system prompt, its own tools, and can even use a different AI model. The analyst might use a reasoning model while the writer uses a creative one.

## When to use multiple agents

**Different skills needed** — An analysis task and a writing task need different prompts and tools.

**Different LLMs** — One agent uses Ollama locally, another uses GPT-4o for harder tasks.

**Independent scaling** — The support agent gets 100x more traffic than the report agent. Scale them independently.

**Team collaboration** — Agents discuss a topic, each contributing their expertise, then synthesize a conclusion.

## How it works in ABI-Core

```bash
# Create project where agents can find each other
abi-core create project my-system --with-semantic-layer

# Add specialized agents
abi-core add agent analyst --description "Analyzes data and trends"
abi-core add agent writer --description "Writes reports and summaries"
```

Each agent gets:
- Its own container (runs independently)
- Its own agent card (so others can find it)
- Its own messaging endpoint (so others can talk to it)

Agents find each other by describing what they need:

```python
# "Who can write reports?" → finds the writer agent
agent = await tool_find_agent("write reports")
```

## Next step

👉 [Agent Cards](02-agent-cards.md)
