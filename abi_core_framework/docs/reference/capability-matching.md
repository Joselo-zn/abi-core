# Capability Matching

```{note}
**Alpha.** `abi_core.capabilities` ships the data model, matching logic, and a
dev-time model profiler (probes + Wilson intervals + CLI). It is not yet wired
into the agents — the cycle (orchestrator → planner → builder → ephemeral)
consumes it in later phases.
```

## The idea: characterize the task, then assign capability

The usual question is *"which model should we use?"*. A more useful one is
*"what capabilities does the task require?"*. Prompts express **intent**, but LLMs
predict the most probable path toward an *inferred* objective — they don't
guarantee compliance. And the more capable a model, the more it optimizes for the
inferred goal over strict instruction-following.

So instead of tuning prompts forever to force behavior, ABI-Core lets you profile
a **task** by what it needs and a **model** by what it provides, over the same
dimensions, and compare them. When a model can't cover a requirement, that's a
signal to either pick a different model or close the gap with a structural
reinforcement — not to add more prompt.

## The 7 dimensions

A capability profile is a vector of 7 scores in `[0.0, 1.0]`:

| Dimension | Measures |
|-----------|----------|
| `code_generation` | Producing correct, complete code |
| `tool_usage` | Reliably invoking tools / emitting tool calls |
| `reasoning` | Logic, inference, problem solving |
| `planning` | Decomposing and sequencing sub-tasks |
| `structured_output` | Emitting strict formats (JSON/schema) |
| `context_span` | Staying coherent over long context |
| `instruction_following` | Adhering to instructions vs. optimizing for the inferred goal |

`instruction_following` is the key axis: it explains why a small model can be a
better orchestrator than a large one — orchestration needs adherence and
structured output, not raw reasoning power.

```{note}
Operational **constraints** (latency, cost, memory) are *not* capabilities. They
belong to a separate axis applied as a later filter, so "it's fast" never
compensates for "it can't generate code".
```

## Quick start

```python
from abi_core.capabilities import (
    CapabilityProfile, TaskProfile, select_model, seed_catalog,
)

# What does this task require?
task = TaskProfile(capabilities=CapabilityProfile(
    code_generation=0.9,
    tool_usage=0.95,
    instruction_following=0.6,
))

# Match against the available models.
result = select_model(task, seed_catalog())

result.model_name   # best-matching model
result.score        # scalar match in [0,1] (1.0 = fully covered)
result.gaps         # {dimension: deficit} to reinforce
result.ranked       # full ranking, best first
```

### Scoring

`match_score(task, model)` returns a scalar in `[0,1]`:

```
score = 1 - (Σ weightᵈ · max(0, requiredᵈ - providedᵈ)) / (Σ weightᵈ)
```

over the dimensions the task actually requires. **Only deficit is penalized** —
surplus capability neither rewards nor penalizes. Picking "the biggest model" is
not the goal; covering the task's requirements is.

Tasks can weight dimensions explicitly when one matters more than its raw
requirement suggests:

```python
task = TaskProfile(
    capabilities=CapabilityProfile(tool_usage=1.0, reasoning=1.0),
    weights={"tool_usage": 3.0, "reasoning": 1.0},   # tool_usage dominates
)
```

## Where model profiles come from

Profiling a model is a **dev-time** step, not a runtime cost. Because you already
know your candidate models before building, you profile them once, export a JSON
catalog, load it into the agentic system, and let runtime refine it:

```
profile (dev time, offline)  →  export JSON  →  load into system  →  refine at runtime
```

- **Seed** — honest qualitative estimates shipped with the framework
  (`source="seed"`, `samples=0`), so matching works out of the box.
- **Loaded JSON** — a catalog you profiled/authored, loaded at deploy time (no
  expensive cold-start benchmarking on every boot).
- **Measured/refined** — each real execution nudges the scores toward reality via
  a running mean.

```python
from abi_core.capabilities import get_seed_profile, load_profiles, save_profiles

# Load a catalog you profiled at dev time
profiles = load_profiles("model_profiles.json")

# Refine from an observed execution (running mean; marks the profile "measured")
mp = get_seed_profile("devstral:24b")
mp = mp.with_observation("tool_usage", 0.9)

# Persist a catalog back to JSON
save_profiles(profiles, "model_profiles.json", generator="my-benchmark")
```

`seed_catalog(models=[...])` returns only the profiles for the models actually
pulled on a node.

## Visualizing profiles (CLI)

Inspect a profile as terminal bars, or overlay a task requirement against a model
to see the gap:

```bash
# List models in a source (seed catalog by default, or a JSON file)
abi-core capabilities list
abi-core capabilities list --source model_profiles.json

# Show one model's profile as terminal bars
abi-core capabilities show devstral:24b

# Also write a radar (spider) chart PNG (requires the optional 'viz' extra)
abi-core capabilities show devstral:24b --radar devstral.png
```

The radar chart requires matplotlib (`pip install "abi-core-ai[viz]"`); the
terminal bars work without it.

## Measuring a model (dev-time)

`abi-core capabilities profile` runs a **deterministic probe battery** against a
model and writes a measured profile to JSON:

```bash
abi-core capabilities profile qwen2.5:3b \
  --host http://localhost:11434 \
  --output qwen_profile.json \
  --n-min 10 --n-max 40
```

How it works:

- Each of the 7 dimensions has several code-verifiable probes of varying
  difficulty (e.g. `structured_output` → is the reply valid JSON?; `tool_usage` →
  did it name the right tool?; `reasoning` → is the single answer correct?). No LLM
  judge — the verifier is deterministic, so the measurement isn't itself noisy.
- Each probe is repeated N times (the model is non-deterministic) and scored as a
  success ratio with a **Wilson 95% confidence interval**. Sampling stops early
  once the interval is narrow enough, between `--n-min` and `--n-max`.
- Dimension scores are a difficulty-weighted mean of their probes, on an absolute
  0–1 scale (not relative to other models).
- The JSON records provenance (`probe_suite_version`, host, temperature, per-probe
  results) for reproducibility.

Load the result back with `--source qwen_profile.json` on `list`/`show`, or with
`load_profiles()` in code. Runtime executions can then refine it further via
`ModelProfile.with_observation()`.

## What comes next

Phase 0 is foundations only. Later phases wire this into the cycle: the Planner
derives a `TaskProfile` per atomic task, the Builder uses `select_model` to choose
a model and an execution architecture, and the ephemeral agent applies the chosen
reinforcement (e.g. a code-extraction layer when `tool_usage` is the gap). See the
capability-matching spec for the full roadmap.
