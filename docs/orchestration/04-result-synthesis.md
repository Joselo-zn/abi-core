# Result Synthesis

The Orchestrator combines results from multiple agents into a coherent response.

## How It Works

1. Agents execute their tasks
2. Each agent returns a result
3. Orchestrator uses LLM to synthesize
4. User receives unified response

## Example

```
Agent 1: "Sales: $100,000"
Agent 2: "Growth: 15%"
Agent 3: "Top product: Widget A"

Synthesis:
"Sales reached $100,000 with 15% growth.
The best-selling product was Widget A."
```

## Next Steps

- [RAG & Knowledge](../rag/01-what-is-rag.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
