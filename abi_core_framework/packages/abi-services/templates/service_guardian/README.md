# Guardian — OPA Infrastructure Template

The Guardian **agent** code has been migrated to `packages/abi-agents/src/abi_agents/guardian/`.

This template now only contains the **OPA infrastructure** that is project-specific:

- `opa/` — OPA server Dockerfile and policy files
- `opa/policies/` — Project-specific Rego policies

## What the CLI does

When you run `abi-core add service guardian-native`, the CLI:

1. Copies the Guardian agent from `abi-agents` into your project's `agents/` directory
2. Renders the OPA Dockerfile and policies from this template into `services/guardian/opa/`
3. Adds both to `compose.yaml`

## Policy structure

```
opa/
├── Dockerfile.j2          # OPA server container
└── policies/
    ├── core_security.rego  # Immutable core policies (auto-generated)
    └── custom/             # Project-specific policies (user-defined)
```
