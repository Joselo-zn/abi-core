# Builder Agent

ABI Builder Agent — scaffolds and builds ABI projects, agents, and services.

## Port

- Agent: `11439`

## Usage

```python
from builder import AbiBuilderAgent
from abi_core.agent import AbiCore

agent = AbiCore()
agent.run(AbiBuilderAgent())
```
