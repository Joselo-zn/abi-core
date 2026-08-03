# Background & Scheduled Tasks — Work That Doesn't Wait

```{note}
**Alpha.** `@agent.task_async` and `@agent.task_schedule` are under active
development. The API may change between releases.
```

Not everything an agent does fits inside a request/response cycle. Some work is too slow to make a user wait for (crunching a report, calling a flaky third-party API). Some work isn't triggered by a user at all — it should just happen, on a schedule, forever (checking infrastructure health every night, cleaning up stale data every hour).

`@agent.step` and `@agent.task` don't cover either case — both are tied to a single request. This page adds two decorators that are:

- **`@agent.task_async`** — fire-and-forget. Kick it off, get an id back immediately, check on it later.
- **`@agent.task_schedule`** — recurring. Register it once; it fires on its own from then on.

## What you'll build

An agent that:
1. Starts a slow analysis in the background and replies to the user immediately with a tracking id
2. Lets the user (or another task) check on that background job's status
3. Runs a health-check every night, on its own, with no HTTP request involved

## Fire-and-forget: `@agent.task_async`

Register it just like a step or a task — the difference is nobody `await`s it directly:

```python
from app import agent

@agent.task_async(name="analyze_dataset", max_retries=3, base_delay=1.0)
async def analyze_dataset(dataset_url: str):
    """The slow part. This can take minutes — the caller doesn't wait for it."""
    data = await download(dataset_url)
    return {"rows": len(data), "summary": summarize(data)}
```

From a task, launch it with `execute_task_async` — this returns instantly, it does **not** wait for `analyze_dataset` to finish:

```python
@agent.task(name="start_analysis", task_id="task-start-analysis")
async def start_analysis(dataset_url, context_id=None):
    async_task_id = await agent.execute_task_async(
        "analyze_dataset", dataset_url=dataset_url, context_id=context_id
    )
    yield AgentResponse.result({
        "message": "Analysis started — check back with this id.",
        "async_task_id": async_task_id,
    })
```

Give the user (or a scheduled job, or another agent) a way to check on it — `get_async_task_status` is a plain in-process lookup, no extra infrastructure needed:

```python
@agent.task(name="check_analysis", task_id="task-check-analysis")
async def check_analysis(async_task_id):
    status = await agent.get_async_task_status(async_task_id)
    if status is None:
        yield AgentResponse.error("Unknown task id.")
        return
    yield AgentResponse.result(status)
```

`status` looks like this once it's done:

```python
{
    "async_task_id": "atask-4f9a2c8e1b03",
    "name": "analyze_dataset",
    "status": "done",          # "running" | "done" | "failed"
    "attempts": 1,
    "error": None,
    "result": {"rows": 42000, "summary": "..."},
    "started_at": 1785700000.0,
    "finished_at": 1785700042.0,
}
```

### If it fails

A failed `task_async` retries with real exponential backoff (`base_delay`, `2×`, `4×`, ...) before giving up — every attempt is logged, so nothing fails silently. Add callbacks if you want to react immediately instead of polling:

```python
async def notify_done(async_task_id, result):
    ...

async def notify_failed(async_task_id, error):
    ...

@agent.task_async(name="analyze_dataset", on_success=notify_done, on_error=notify_failed)
async def analyze_dataset(dataset_url: str):
    ...
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | `3` | Retry attempts before giving up |
| `base_delay` | `1.0` | Seconds before the first retry (doubles each attempt) |
| `on_success` | — | `(async_task_id, result)` callback |
| `on_error` | — | `(async_task_id, error)` callback, called once retries are exhausted |

## Recurring jobs: `@agent.task_schedule`

A scheduled job isn't just a cron entry — it's a background task that decides for itself, every time it wakes up, whether it should actually run:

```python
@agent.task_schedule(
    name="nightly_health_check",
    trigger="cron",
    trigger_args={"hour": 3, "minute": 0},
)
async def nightly_health_check():
    """Runs every night at 3am — no request, no user, no A2A call involved."""
    issues = await check_infrastructure()
    if issues:
        await alert_team(issues)
    return {"issues_found": len(issues)}
```

`trigger` and `trigger_args` are passed straight through to [APScheduler](https://apscheduler.readthedocs.io/) — `"interval"` (`{"seconds": 300}`, `{"minutes": 5}`, ...), `"cron"` (`{"hour": 3}`, `{"day_of_week": "mon"}`, ...), or `"date"` (a one-off run).

### Two things a "just a cron job" doesn't do for you

**It won't pile up on itself.** If `nightly_health_check` is still running when its next firing comes around (a slow night), the default `overlap_policy="skip"` drops the new firing instead of running two at once:

```python
@agent.task_schedule(
    name="nightly_health_check",
    trigger="cron",
    trigger_args={"hour": 3, "minute": 0},
    overlap_policy="skip",       # default — at most one instance at a time
)
```

Need concurrency instead? `overlap_policy="allow"` + `max_concurrent=N`.

**It asks permission before every firing, not just once.** If your project has a Guardian/OPA setup (`abi-core add abi-swarm` or `--with-guardian`), every firing is gated by an OPA policy check — `abi/scheduled_task/allow` by default. No Guardian provisioned? It fails **open** (runs anyway, with a logged warning) — this is opt-in governance, not a hard requirement:

```python
@agent.task_schedule(
    name="nightly_health_check",
    trigger="cron",
    trigger_args={"hour": 3, "minute": 0},
    fail_mode="closed",          # want it to require OPA instead? opt in.
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `trigger` | — | `"cron"`, `"interval"`, or `"date"` |
| `trigger_args` | — | Passed to APScheduler as-is |
| `overlap_policy` | `"skip"` | `"skip"` drops overlapping firings, `"allow"` permits `max_concurrent` |
| `fail_mode` | `"open"` | `"open"` runs if OPA is unreachable, `"closed"` denies |
| `max_retries` / `base_delay` | `3` / `1.0` | Same retry behavior as `task_async` |

## Enabling scheduled jobs

`@agent.task_schedule` needs [APScheduler](https://apscheduler.readthedocs.io/) — add it to your agent's `requirements.txt` only if you actually use it:

```
abi-core-ai[scheduler]
```

An agent with zero `@agent.task_schedule` registrations never imports it and pays no cost.

## Choosing a status backend

Where does `get_async_task_status` actually look? By default, in the agent's own process memory — fine for development, but it means a `task_schedule`'s "is the previous run still going?" check only sees firings from *this* replica. For production with multiple replicas, point it at Redis instead (the same one `abi-core add service agent-memory` already gives you):

```bash
ASYNC_TASK_BACKEND=redis
```

See [Environment Variables](../reference/environment-variables.md#async-task-backend) for the full reference.

## What happened

1. `start_analysis` called `execute_task_async(...)`, which scheduled `analyze_dataset` to run in the background and returned an id **without waiting** for it
2. The user got an immediate reply — "Analysis started" — instead of a request that hangs for minutes
3. `analyze_dataset` ran on its own; if it failed, it retried with backoff before giving up
4. `check_analysis` (or `get_async_task_status` from anywhere else in the agent) read the result once it was ready
5. `nightly_health_check` never waited for any of this — APScheduler wakes it up on its own schedule, checks it isn't already running, checks OPA, then runs it

## Key rules

- **`task_async` is for one-off work that shouldn't block a response.** If it always needs to finish before you can reply, you don't need it — just `await` it directly inside a normal `@agent.task`.
- **`task_schedule` is for work nobody explicitly triggers.** If a user or another agent is supposed to ask for it, it's a `@agent.task`, not a schedule.
- **Status is in-process by default — not persisted across restarts.** Use `ASYNC_TASK_BACKEND=redis` if you need it to survive a restart or be visible across replicas.
- **A `task_schedule` firing that gets skipped for overlap never asks OPA.** If it's not going to run, there's no point asking permission first.
- **Neither decorator needs Guardian/OPA to work.** They're both opt-in governance layers — a project without them still runs fine, just without the extra gate.

## Next step

👉 [Troubleshooting](03-troubleshooting.md)
