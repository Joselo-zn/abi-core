# Why Multiple Agents?

Learn when and why to use multiple agents instead of one.

## The Problem with One Agent

One agent doing everything:
```
Universal Agent
├─ Analyzes data
├─ Writes code
├─ Translates languages
├─ Answers questions
├─ Generates reports
└─ ... (does everything poorly)
```

**Problems**:
- ❌ Not expert in anything
- ❌ Generic responses
- ❌ Hard to maintain
- ❌ Not scalable

## The Solution: Specialized Agents

Multiple agents, each expert:
```
Multi-Agent System
├─ Analyst Agent → Expert in analysis
├─ Programmer Agent → Expert in code
├─ Translator Agent → Expert in languages
└─ Reporter Agent → Expert in reports
```

**Advantages**:
- ✅ Each agent is expert
- ✅ Specialized responses
- ✅ Easy to maintain
- ✅ Scalable

## When to Use Multiple Agents

### Case 1: Complex Tasks

**Task**: "Analyze last month's sales and generate a PDF report"

**With one agent**: Does everything poorly
**With multiple agents**:
1. Analyst Agent → Analyzes sales
2. Reporter Agent → Generates PDF

### Case 2: Different Domains

**Project**: E-commerce system

**Agents needed**:
- Product Agent (catalog)
- Sales Agent (transactions)
- Support Agent (customer help)
- Inventory Agent (stock)

### Case 3: Scalability

**Problem**: One agent can't handle the load

**Solution**: Multiple instances of the same agent
```
User 1 → Agent A
User 2 → Agent B
User 3 → Agent C
```

## Multi-Agent Architecture

```
User
  ↓
Orchestrator (coordinates)
  ↓
├─ Agent 1 (specialist)
├─ Agent 2 (specialist)
└─ Agent 3 (specialist)
  ↓
Combined result
```

## Practical Example

### Financial Analysis System

```bash
# Create project
abi-core create project finance --with-semantic-layer

# Agent 1: Data collector
abi-core add agent collector \
  --description "Collects financial data"

# Agent 2: Analyst
abi-core add agent analyst \
  --description "Analyzes financial data"

# Agent 3: Reporter
abi-core add agent reporter \
  --description "Generates reports"
```

**Flow**:
1. User: "Analyze Apple stock"
2. Collector → Gets Apple data
3. Analyst → Analyzes the data
4. Reporter → Generates report
5. User receives complete report

## Next Steps

- [Agent Cards](02-agent-cards.md)
- [Agent communication](03-agent-communication.md)
- [Your first multi-agent system](04-first-multi-agent-system.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
