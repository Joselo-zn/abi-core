# Migrating to a2a-sdk 1.0

Starting with abi-core-ai v1.12, the framework requires `a2a-sdk>=1.0.0`. This version changed `AgentCard` from a pydantic model to a protobuf message, which means it no longer accepts arbitrary fields.

## Who is affected?

- **Projects running on the ABI Docker image**: Not affected. The image pins `a2a-sdk==0.3.25`.
- **Projects that install `abi-core-ai` directly from PyPI**: You need to update your `config.py`.

## What changed

| Before (0.3.x) | After (1.0+) |
|-----------------|--------------|
| `AgentCard` is pydantic | `AgentCard` is protobuf |
| Accepts any kwargs | Only accepts protocol fields |
| `card.url` | `card.supported_interfaces[0].url` |
| `AgentCard(**json_data)` | `load_agent_card(path)` or `build_agent_card(dict)` |

## How to migrate your config.py

**Before:**
```python
from a2a.types import AgentCard

def _load_agent_card():
    with open(config.AGENT_CARD) as f:
        data = json.load(f)
    return AgentCard(**data)
```

**After:**
```python
from a2a.types import AgentCard
from abi_core.common.agent_card_loader import load_agent_card

def _load_agent_card():
    card, _meta = load_agent_card(config.AGENT_CARD)
    return card
```

The `_meta` dict contains ABI-specific fields that are no longer part of the protocol:
- `meta["auth"]` — HMAC credentials
- `meta["id"]` — agent identifier
- `meta["supportedTasks"]` — task list for semantic layer
- `meta["llmConfig"]` — LLM configuration
- `meta["url"]` — agent URL (backward compat)

## Accessing the agent URL

**Before:**
```python
url = card.url
```

**After:**
```python
from abi_core.common.agent_card_loader import get_agent_url
url = get_agent_url(card)
```

## Agent card JSON files

No changes needed. Your `agent_cards/*.json` files keep all the same fields. The loader separates protocol fields from ABI metadata automatically.

## New projects

Projects created with `abi-core create agent` (v1.12+) already use the new pattern. No action needed.
