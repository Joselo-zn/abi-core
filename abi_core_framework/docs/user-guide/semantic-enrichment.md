# Semantic Enrichment Guide

## Overview

Semantic enrichment is the process of adding contextual metadata to agent inputs to enable intelligent routing, discovery, and processing. ABI-Core provides built-in semantic enrichment capabilities through the `abi_core.agent.semantics` module.

## What is Semantic Enrichment?

When an agent receives input, semantic enrichment:

1. **Normalizes** the input format (string, dict, etc.)
2. **Adds semantic context** for agent discovery
3. **Extracts intent** from the query
4. **Prepares data** for semantic layer routing

This enables agents to understand not just what the input is, but what it means and how it should be processed.

## Core Functions

### `enrich_input()`

Enriches raw input with semantic metadata.

**Signature:**
```python
def enrich_input(input_data: Any) -> Dict[str, Any]
```

**Parameters:**
- `input_data`: Raw input (string, dict, or other types)

**Returns:**
Dictionary containing:
- `query`: Processed query string
- `raw_input`: Original input data
- `input_type`: Type classification (text, structured, unknown)
- `semantic_context`: Semantic metadata
- `metadata`: Enrichment metadata

**Example:**
```python
from abi_core.agent.semantics import enrich_input

# String input
result = enrich_input("Find an agent for data analysis")

print(result)
# Output:
# {
#     'query': 'Find an agent for data analysis',
#     'raw_input': 'Find an agent for data analysis',
#     'input_type': 'text',
#     'semantic_context': {
#         'intent': 'agent_discovery',
#         'requires_routing': True,
#         'discovery_enabled': True
#     },
#     'metadata': {
#         'enriched_at': '2025-01-21T10:30:00.000000',
#         'enrichment_version': '1.0.0'
#     }
# }
```

**Dict Input:**
```python
# Structured input
result = enrich_input({
    'query': 'Analyze sales data',
    'filters': {'region': 'US'},
    'limit': 100
})

print(result['input_type'])  # 'structured'
print(result['query'])        # 'Analyze sales data'
```

### `extract_intent()`

Detects the intent from a query string.

**Signature:**
```python
def extract_intent(query: str) -> str
```

**Parameters:**
- `query`: User query string

**Returns:**
Intent classification: `search`, `execute`, `analyze`, or `general`

**Example:**
```python
from abi_core.agent.semantics import extract_intent

# Search intent
intent = extract_intent("find an agent for trading")
print(intent)  # 'search'

# Execute intent
intent = extract_intent("execute the backup task")
print(intent)  # 'execute'

# Analyze intent
intent = extract_intent("analyze customer behavior")
print(intent)  # 'analyze'

# General intent
intent = extract_intent("hello, how are you?")
print(intent)  # 'general'
```

**Intent Detection Logic:**

| Keywords | Intent |
|----------|--------|
| find, search, discover, locate | `search` |
| execute, run, perform, do | `execute` |
| analyze, process, compute | `analyze` |
| (other) | `general` |

### `prepare_for_semantic_layer()`

Prepares enriched data for semantic layer consumption.

**Signature:**
```python
def prepare_for_semantic_layer(enriched_data: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters:**
- `enriched_data`: Output from `enrich_input()`

**Returns:**
Formatted data for semantic layer with:
- `query`: The query string
- `intent`: Detected intent
- `context`: Semantic context
- `metadata`: Enrichment metadata

**Example:**
```python
from abi_core.agent.semantics import enrich_input, prepare_for_semantic_layer

# Enrich input
enriched = enrich_input("Find a trading agent")

# Prepare for semantic layer
semantic_data = prepare_for_semantic_layer(enriched)

print(semantic_data)
# Output:
# {
#     'query': 'Find a trading agent',
#     'intent': 'search',
#     'context': {
#         'intent': 'agent_discovery',
#         'requires_routing': True,
#         'discovery_enabled': True
#     },
#     'metadata': {
#         'enriched_at': '2025-01-21T10:30:00.000000',
#         'enrichment_version': '1.0.0'
#     }
# }
```

## Integration with Agents

### Using in AbiAgent

The `AbiAgent` class automatically uses semantic enrichment:

```python
from abi_core.agent.agent import AbiAgent

class MyAgent(AbiAgent):
    def process(self, enriched_input):
        # enriched_input already contains semantic context
        query = enriched_input['query']
        intent = enriched_input['semantic_context']['intent']
        
        if intent == 'agent_discovery':
            return self.handle_discovery(query)
        else:
            return self.handle_general(query)
    
    def handle_discovery(self, query):
        return {"result": f"Discovering agents for: {query}"}
    
    def handle_general(self, query):
        return {"result": f"Processing: {query}"}

# Usage
agent = MyAgent("my-agent", "My agent", ["text/plain"])
result = agent.handle_input("Find a data analyst agent")
print(result)
```

### Manual Enrichment

For custom agents, use enrichment manually:

```python
from abi_core.agent.base_agent import BaseAgent
from abi_core.agent.semantics import enrich_input
from abi_core.agent.policy import evaluate_policy

class CustomAgent(BaseAgent):
    def process_query(self, raw_input):
        # Enrich input
        enriched = enrich_input(raw_input)
        
        # Evaluate policies
        if not evaluate_policy(enriched):
            raise PermissionError("Policy rejected input")
        
        # Process based on intent
        intent = enriched['semantic_context']['intent']
        query = enriched['query']
        
        if intent == 'agent_discovery':
            return self.discover_agents(query)
        else:
            return self.process_general(query)
```

## Complete Workflow Example

Here's a complete example showing the enrichment pipeline:

```python
from abi_core.agent.semantics import (
    enrich_input,
    extract_intent,
    prepare_for_semantic_layer
)
from abi_core.agent.policy import evaluate_policy

def process_user_query(user_input: str):
    """Complete semantic enrichment pipeline"""
    
    # Step 1: Enrich input
    print("Step 1: Enriching input...")
    enriched = enrich_input(user_input)
    print(f"  Query: {enriched['query']}")
    print(f"  Type: {enriched['input_type']}")
    print(f"  Intent: {enriched['semantic_context']['intent']}")
    
    # Step 2: Evaluate policies
    print("\nStep 2: Evaluating policies...")
    if not evaluate_policy(enriched):
        print("  ❌ Policy rejected")
        return None
    print("  ✅ Policy approved")
    
    # Step 3: Extract intent
    print("\nStep 3: Extracting intent...")
    intent = extract_intent(enriched['query'])
    print(f"  Detected intent: {intent}")
    
    # Step 4: Prepare for semantic layer
    print("\nStep 4: Preparing for semantic layer...")
    semantic_data = prepare_for_semantic_layer(enriched)
    print(f"  Ready for routing: {semantic_data['query']}")
    
    return semantic_data

# Example usage
if __name__ == "__main__":
    queries = [
        "Find an agent for financial analysis",
        "Execute the daily report generation",
        "Analyze customer sentiment from reviews"
    ]
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Processing: {query}")
        print('='*60)
        result = process_user_query(query)
        if result:
            print(f"\n✅ Final result: {result}")
```

**Output:**
```
============================================================
Processing: Find an agent for financial analysis
============================================================
Step 1: Enriching input...
  Query: Find an agent for financial analysis
  Type: text
  Intent: agent_discovery

Step 2: Evaluating policies...
  ✅ Policy approved

Step 3: Extracting intent...
  Detected intent: search

Step 4: Preparing for semantic layer...
  Ready for routing: Find an agent for financial analysis

✅ Final result: {'query': 'Find an agent for financial analysis', 'intent': 'search', ...}
```

## Best Practices

### 1. Always Enrich Before Processing

```python
# ✅ Good
enriched = enrich_input(user_input)
result = agent.process(enriched)

# ❌ Bad
result = agent.process(user_input)  # Missing enrichment
```

### 2. Check Intent Before Routing

```python
enriched = enrich_input(query)
intent = enriched['semantic_context']['intent']

if intent == 'agent_discovery':
    # Route to semantic layer
    agent = semantic_layer.find_agent(query)
else:
    # Process directly
    result = agent.process(enriched)
```

### 3. Preserve Original Input

```python
enriched = enrich_input(user_input)

# Original input is preserved
original = enriched['raw_input']
processed = enriched['query']

# Can compare or log both
logger.info(f"Original: {original}")
logger.info(f"Processed: {processed}")
```

### 4. Use Metadata for Debugging

```python
enriched = enrich_input(query)
metadata = enriched['metadata']

logger.debug(f"Enriched at: {metadata['enriched_at']}")
logger.debug(f"Version: {metadata['enrichment_version']}")
```

## Advanced Usage

### Custom Intent Detection

Extend intent detection for domain-specific needs:

```python
from abi_core.agent.semantics import extract_intent

def custom_intent_detection(query: str) -> str:
    """Custom intent detection with domain-specific logic"""
    
    # Use base detection
    base_intent = extract_intent(query)
    
    # Add custom logic
    query_lower = query.lower()
    
    if 'trade' in query_lower or 'buy' in query_lower or 'sell' in query_lower:
        return 'trading'
    elif 'report' in query_lower or 'dashboard' in query_lower:
        return 'reporting'
    elif 'alert' in query_lower or 'notify' in query_lower:
        return 'alerting'
    
    return base_intent

# Usage
intent = custom_intent_detection("Buy 100 shares of AAPL")
print(intent)  # 'trading'
```

### Enrichment with Additional Context

Add custom context to enriched data:

```python
from abi_core.agent.semantics import enrich_input

def enrich_with_user_context(query: str, user_id: str, session_id: str):
    """Enrich with additional user context"""
    
    # Base enrichment
    enriched = enrich_input(query)
    
    # Add custom context
    enriched['user_context'] = {
        'user_id': user_id,
        'session_id': session_id,
        'timestamp': enriched['metadata']['enriched_at']
    }
    
    return enriched

# Usage
enriched = enrich_with_user_context(
    "Find a trading agent",
    user_id="user123",
    session_id="sess456"
)
```

## Next Steps

- [Policy Development](policy-development.md) - Learn about policy evaluation
- [Agent Development](agent-development.md) - Build custom agents
- [Semantic Layer](semantic-layer.md) - Configure agent discovery

## See Also

- [API Reference](../api/semantics.md)
- [Architecture](../architecture.md)
- [FAQ](../faq.md)
