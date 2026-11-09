# Code Execution Sandbox

Generated code has to run before anyone can say it works: a set of files can compile one by one and still crash the moment they run together. The sandbox runs that code in a throwaway container with no network, no credentials and hard limits, and returns a diagnosis — exit code, output, and an optional JSON result.

The caller decides **what** runs (the command), never an LLM. Everything that comes back is untrusted data.

## Guarantees

| Guarantee | How (Docker backend) |
|-----------|----------------------|
| No network | `network_mode=none` — neither the internet nor other services |
| No credentials | Only allowlisted variables reach the sandbox; anything else is rejected before the container exists |
| Not root | Runs as uid 10001 with all capabilities dropped and `no-new-privileges` |
| Read-only system | Root filesystem read-only; `/workspace` is a size-limited tmpfs |
| Limits | Wall clock, CPU, memory (no swap), PIDs, output size |
| Throwaway | One container per call, always removed |

## Usage

```python
from abi_core.common.sandbox import run_in_sandbox, SandboxLimits, SANDBOX_IMAGE_PYGAME

result = await run_in_sandbox(
    files={"game.py": source.encode(), "player.py": player_src.encode()},
    command=["python", "game.py"],
    image=SANDBOX_IMAGE_PYGAME,
    env={"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
    limits=SandboxLimits(timeout_s=30),
)

if result.timed_out: ...
elif result.exit_code != 0:
    print(result.stderr)   # tail kept — the traceback is at the bottom
```

`SandboxResult` fields: `exit_code`, `timed_out`, `oom_killed`, `stdout`, `stderr`, `stdout_truncated`, `stderr_truncated`, `result_json`, `duration_s`, `error` (the sandbox itself failed, not the code), and `ok`.

### Returning structured results

If the command writes `/workspace/.result.json`, it comes back in `result.result_json` as raw text (max 256 KiB; 128 KiB on Cloud Run). Parse it; never execute or trust it — it was produced by the code under test.

### Allowed environment variables

`SDL_VIDEODRIVER`, `SDL_AUDIODRIVER`, `PYTHONHASHSEED`, `LANG`, `LC_ALL`, `TZ`, and any `ABI_ACCEPTANCE_*`. Anything else raises `ValueError`.

## Default limits

| Limit | Default | Notes |
|-------|---------|-------|
| `timeout_s` | 60 | 1–300 |
| `cpus` | 1.0 | |
| `memory_mb` | 512 | No swap; exceeding it sets `oom_killed` |
| `pids` | 128 | Contains fork bombs |
| `workspace_mb` | 64 | tmpfs at `/workspace` |
| `max_output_bytes` | 64 KiB | Per stream, tail kept |
| `max_result_bytes` | 256 KiB | `.result.json` (128 KiB on Cloud Run) |

Files are passed as a compressed bundle of at most 1 MiB (encoded).

## Images

Build them once from `abi_core_framework/sandbox-images`:

```bash
docker build -f python/Dockerfile -t abi-sandbox-python:latest .
docker build -f pygame/Dockerfile -t abi-sandbox-pygame:latest .
docker build -f data/Dockerfile -t abi-sandbox-data:latest .
```

| Image | Contents |
|-------|----------|
| `abi-sandbox-python` | Python 3.12 + numpy |
| `abi-sandbox-pygame` | The above + pygame (headless with `SDL_VIDEODRIVER=dummy`) |
| `abi-sandbox-data` | `abi-sandbox-python` + pandas 2.3.3 and openpyxl 3.1.5, for data analysis. Constant: `SANDBOX_IMAGE_DATA` |

Build `abi-sandbox-python` first: the other two start from it.

There is no network at run time, so nothing is installed during a run. A deliverable that imports a package the image doesn't have fails with `ModuleNotFoundError` — report it as a finding.

## Who can call it

With `SANDBOX_RUNTIME=docker` (default), the process calling `run_in_sandbox` needs the Docker socket. Agents get no tool to run code in the sandbox.

## Governed sandbox (`SANDBOX_RUNTIME=service`)

With `SANDBOX_RUNTIME=service`, callers never touch Docker. `run_in_sandbox` sends the run to **sandbox-service** (`python -m abi_services.sandbox_service`), the only component that holds the Docker socket. Every request:

- **is signed** with the caller's agent card, over everything it asks to run — command, image, environment, limits and files — so a signature can't be reused for different code;
- **is checked against the caller's identity** by the Semantic Layer;
- **belongs to a plan run** and is checked against that run;
- **is decided by OPA** (`abi/sandbox`) — and denied if OPA can't be reached;
- **is audited**, allowed or denied.

A caller needs the permission in its agent card:

```json
"security": {"allowed_actions": ["run_sandbox"]}
```

and runs code from a step or task decorated with `@agent.sandboxed`, which takes the plan run's id as `run_id`:

```python
@agent.step(name="check", input_map={"run_id": "$input.run_id"})
@agent.sandboxed
async def check(run_id):
    result = await run_in_sandbox(files, ["python", "main.py"])
```

A data analysis has no plan. A caller whose card lists `run_sandbox_data` instead may run in the `abi-sandbox-data` image without one, with the same limit on runs per `run_id`; any other image still needs `run_sandbox`, a plan and an entry point.

```json
"security": {"allowed_actions": ["run_sandbox_data"]}
```

Outside a decorated function, `with sandbox_caller(run_id): ...` (`abi_core.common.sandbox_service_client`) does the same. A denied or unreachable service comes back as `SandboxResult.error` (`"sandbox denied: <reason>"`) — never as a pass.

## Running on Cloud Run Jobs (`SANDBOX_RUNTIME=cloudrun`)

On GCP there's no Docker socket to hand out. The Cloud Run backend runs each call as an execution of a **Cloud Run Job**, one Job per sandbox image, with the same contract as Docker: the files, the allowlisted environment and the command travel with each execution, and the same `SandboxResult` comes back.

```bash
pip install "abi-core-ai[gcp]"
```

```bash
SANDBOX_RUNTIME=cloudrun          # or SANDBOX_SERVICE_BACKEND=cloudrun on sandbox-service
CLOUDRUN_PROJECT=my-project
CLOUDRUN_REGION=us-central1
SANDBOX_CLOUDRUN_JOBS=abi-sandbox-python=sandbox-python-prod,abi-sandbox-pygame=sandbox-pygame-prod
```

`SANDBOX_CLOUDRUN_JOBS` maps each image (its name, without registry or tag) to the Job that runs it. An image with no Job is an error — never a silent fallback to another image or backend.

Normally the Cloud Run backend sits behind the governed sandbox (above): callers keep `SANDBOX_RUNTIME=service`, and sandbox-service runs the code on Cloud Run with `SANDBOX_SERVICE_BACKEND=cloudrun`, keeping the signature, OPA decision and audit in front of it.

### Your deploy creates the Jobs — and their isolation

`abi-core` runs the Jobs; it doesn't create them. Each Job is built from a sandbox image, and the isolation comes from how you deploy it:

| Guarantee | How (Cloud Run Jobs) |
|-----------|----------------------|
| Own kernel | Every execution runs in its own microVM |
| No network | Direct VPC egress to a subnet whose firewall denies all egress for the Job's network tag |
| No useful identity | A dedicated service account with **no roles** |
| Limits | CPU and memory are set on the Job (e.g. 1 CPU, 512 MiB); the timeout is set per execution |

```{warning}
Cloud Run doesn't let you block the metadata server: code running in the Job **can** fetch an access token for the Job's service account. That's why the account must have no roles at all. With no roles and no network, a stolen token opens nothing.
```

### What changes from Docker

| | Docker | Cloud Run Jobs |
|---|---|---|
| Time per call | Seconds | About 10–30 s more: starting the microVM, and reading stdout/stderr back from Cloud Logging |
| `.result.json` | Up to 256 KiB | Up to 128 KiB (it travels in one Cloud Logging entry) |
| `cpus`, `memory_mb` | Per call | Fixed by the Job; per call, only `timeout_s` applies |
| Out of memory | Reported by Docker | Inferred from a SIGKILL exit (137 or 247): Cloud Run doesn't report it |

## Hardening

Docker containers share the host kernel. If [gVisor](https://gvisor.dev/) is installed, set `SANDBOX_DOCKER_RUNTIME=runsc` for an extra barrier against kernel-level escapes.

## Cleanup

A crash of the calling process can leave a container behind. `await sweep_sandboxes(max_age_seconds=600)` removes sandbox containers older than that (they carry the label `abi-sandbox=true`).

## Not yet available

- Limits are chosen by the caller's code and only `timeout_s` is capped (300 s); sandbox-service does not cap memory or CPU per request yet.
- Installing dependencies with network access.
- Long-running services (web servers left running).

## Next step

👉 [CLI Reference](../reference/cli-reference.md)
