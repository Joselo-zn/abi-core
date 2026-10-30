"""Cloud Run Jobs backend of the sandbox (sandbox_cloudrun).

The Cloud Run and Cloud Logging APIs are simulated; the live checks against
a project are in the spec. Spec: .abi/specs/not-implemented/code-execution-sandbox.md
"""

import base64
from types import SimpleNamespace

import pytest

run_v2 = pytest.importorskip("google.cloud.run_v2")

from abi_core.common import sandbox, sandbox_cloudrun as cr  # noqa: E402
from abi_core.common.sandbox import RESULT_BEGIN, RESULT_END, SandboxLimits  # noqa: E402

JOBS = "abi-sandbox-python=abi-sandbox-python-alpha,abi-sandbox-pygame=abi-sandbox-pygame-alpha"


@pytest.mark.parametrize("image, key", [
    ("abi-sandbox-python:latest", "abi-sandbox-python"),
    ("northamerica-south1-docker.pkg.dev/p/r/abi-sandbox-pygame:abc123", "abi-sandbox-pygame"),
    ("reg/abi-sandbox-python@sha256:00", "abi-sandbox-python"),
])
def test_image_key_and_job(image, key):
    assert cr.image_key(image) == key
    assert cr.job_for(image, JOBS) == f"{key}-alpha"


def test_an_image_without_a_job_is_an_error():
    with pytest.raises(ValueError, match="no Cloud Run Job"):
        cr.job_for("abi-sandbox-node:latest", JOBS)


def test_bundle_chunks_fit_cloud_run_env_values():
    # Cloud Run rejects an override value over 32 768 bytes (measured).
    import os
    files = {"blob.bin": os.urandom(300 * 1024)}  # incompressible: ~400 KB once encoded
    bundle = sandbox.build_bundle(files)
    assert len(bundle) > 1
    assert all(len(v) <= 32768 for v in bundle.values())
    assert list(bundle) == [f"ABI_SANDBOX_BUNDLE_{i}" for i in range(len(bundle))]


def test_request_carries_bundle_env_command_and_timeout():
    limits = SandboxLimits(timeout_s=45)
    req = cr.build_request("projects/p/locations/r/jobs/j", ["python", "main.py"],
                           {"PYTHONHASHSEED": "0"}, {"ABI_SANDBOX_BUNDLE_0": "xyz"}, limits)
    assert req.name == "projects/p/locations/r/jobs/j"
    over = req.overrides.container_overrides[0]
    assert list(over.args) == ["python", "main.py"]
    env = {e.name: e.value for e in over.env}
    assert env["PYTHONHASHSEED"] == "0" and env["ABI_SANDBOX_BUNDLE_0"] == "xyz"
    # A result printed as one base64 line must fit a Cloud Logging entry.
    assert env["ABI_SANDBOX_MAX_RESULT_BYTES"] == str(128 * 1024)
    assert req.overrides.task_count == 1
    assert req.overrides.timeout.seconds == 45


def _task(exit_code=0, message=""):
    return SimpleNamespace(last_attempt_result=SimpleNamespace(
        exit_code=exit_code, status=SimpleNamespace(message=message)))


@pytest.mark.parametrize("task, outcome", [
    (_task(0), (0, False)),
    (_task(1), (1, False)),
    (_task(0, "Task attempt timed out after 5s"), (None, True)),
    (SimpleNamespace(last_attempt_result=None), (None, False)),
])
def test_attempt_outcome(task, outcome):
    assert cr.attempt_outcome(task) == outcome


def _entry(stream, ts, text, insert="a"):
    return {"logName": f"projects/p/logs/run.googleapis.com%2F{stream.replace('/', '%2F')}",
            "timestamp": ts, "insertId": insert, "textPayload": text}


def test_logs_are_reassembled_in_order_per_stream():
    entries = [  # newest first, as the API returns them
        _entry("varlog/system", "2026-10-29T00:00:09Z", "Container called exit(1)."),
        _entry("stderr", "2026-10-29T00:00:05Z", "TypeError: boom"),
        _entry("stdout", "2026-10-29T00:00:04Z", "second"),
        _entry("stderr", "2026-10-29T00:00:03Z", "Traceback (most recent call last):"),
        _entry("stdout", "2026-10-29T00:00:02Z", "first"),
    ]
    out, err, system = cr.assemble_logs(entries)
    assert out == "first\nsecond"
    assert err == "Traceback (most recent call last):\nTypeError: boom"
    assert "exit(1)" in system


@pytest.mark.parametrize("system, code, oom", [
    ("Memory limit of 512 MiB exceeded with 530 MiB used.", None, True),
    ("Container called exit(247).", 247, True),   # the program SIGKILLed (measured)
    ("Container called exit(137).", 137, True),   # entry.py itself SIGKILLed
    ("Container called exit(1).", 1, False),
    ("Container called exit(0).", 0, False),
])
def test_oom(system, code, oom):
    assert cr.oom_from(system, code) is oom


class _FakeOperation:
    def __init__(self, execution, fail=False):
        self.metadata = execution
        self._execution, self._fail = execution, fail

    def result(self, timeout=None):
        if self._fail:
            raise RuntimeError("execution failed")
        return self._execution


def _fake_cloud_run(monkeypatch, *, task, logs, fail=False):
    seen = {}
    execution = SimpleNamespace(name="projects/p/locations/r/jobs/abi-sandbox-python-alpha/executions/e-123")

    class Jobs:
        def run_job(self, request):
            seen["request"] = request
            return _FakeOperation(execution, fail)

    class Tasks:
        def list_tasks(self, parent):
            seen["parent"] = parent
            return [task]

    monkeypatch.setattr(run_v2, "JobsClient", Jobs)
    monkeypatch.setattr(run_v2, "TasksClient", Tasks)
    monkeypatch.setattr(cr, "_read_logs", lambda project, execution, finished: seen.setdefault("logs_for", execution) and logs)
    monkeypatch.setenv("CLOUDRUN_PROJECT", "p")
    monkeypatch.setenv("CLOUDRUN_REGION", "r")
    monkeypatch.setenv("SANDBOX_CLOUDRUN_JOBS", JOBS)
    return seen


def test_run_returns_output_result_and_exit_code(monkeypatch):
    payload = base64.b64encode(b'{"can_win": true}').decode()
    logs = [_entry("stdout", "t1", "game started"),
            _entry("stdout", "t2", f"\n{RESULT_BEGIN}\n{payload}\n{RESULT_END}"),
            _entry("varlog/system", "t3", "Container called exit(0).")]
    seen = _fake_cloud_run(monkeypatch, task=_task(0), logs=logs)
    result = cr._run_sync("abi-sandbox-python:latest", ["python", "_acceptance.py"], {},
                          {"ABI_SANDBOX_BUNDLE_0": "x"}, SandboxLimits())
    assert result.error is None and result.ok
    assert result.result_json == '{"can_win": true}'
    assert result.stdout.strip() == "game started"
    assert seen["request"].name == "projects/p/locations/r/jobs/abi-sandbox-python-alpha"
    assert seen["logs_for"] == "e-123"


def test_failed_execution_still_reports_its_exit_code_and_stderr(monkeypatch):
    logs = [_entry("stderr", "t1", "TypeError: object of type 'EnemyFleet' has no len()"),
            _entry("varlog/system", "t2", "Container called exit(1).")]
    _fake_cloud_run(monkeypatch, task=_task(1), logs=logs, fail=True)
    result = cr._run_sync("abi-sandbox-pygame:latest", ["python", "main.py"], {}, {}, SandboxLimits())
    assert result.exit_code == 1 and not result.ok
    assert "EnemyFleet" in result.stderr


def test_timeout_and_oom(monkeypatch):
    _fake_cloud_run(monkeypatch, task=_task(0, "Task attempt timed out"), logs=[], fail=True)
    result = cr._run_sync("abi-sandbox-python:latest", ["python", "loop.py"], {}, {}, SandboxLimits(timeout_s=5))
    assert result.timed_out and result.exit_code is None

    logs = [_entry("varlog/system", "t1", "Container called exit(247).")]
    _fake_cloud_run(monkeypatch, task=_task(247), logs=logs, fail=True)
    result = cr._run_sync("abi-sandbox-python:latest", ["python", "big.py"], {}, {}, SandboxLimits())
    assert result.oom_killed and not result.ok


def test_missing_configuration_is_an_error_result(monkeypatch):
    monkeypatch.delenv("CLOUDRUN_PROJECT", raising=False)
    result = cr._run_sync("abi-sandbox-python:latest", ["python", "x.py"], {}, {}, SandboxLimits())
    assert result.error and "CLOUDRUN_PROJECT" in result.error


def test_run_in_sandbox_dispatches_to_cloudrun(monkeypatch):
    import asyncio
    called = {}

    async def fake_run(image, command, env, bundle, limits):
        called.update(image=image, command=command, bundle=bundle)
        return sandbox.SandboxResult(exit_code=0)

    monkeypatch.setattr(cr, "run", fake_run)
    asyncio.run(sandbox.run_in_sandbox({"main.py": b"print(1)"}, ["python", "main.py"], backend="cloudrun"))
    assert called["command"] == ["python", "main.py"] and "ABI_SANDBOX_BUNDLE_0" in called["bundle"]
