"""
Tests for the code-execution sandbox (abi_core.common.sandbox).

Unit tests (bundle, env allowlist, result framing) always run. Escape and
functional tests need Docker and the sandbox images; they skip otherwise:
    cd abi_core_framework/sandbox-images
    docker build -f python/Dockerfile -t abi-sandbox-python:latest .
    docker build -f pygame/Dockerfile -t abi-sandbox-pygame:latest .

Spec: .abi/specs/not-implemented/code-execution-sandbox.md (Verificación).
"""

import base64
import io
import json
import tarfile
import textwrap

import pytest

from abi_core.common.sandbox import (
    MAX_BUNDLE_BYTES,
    RESULT_BEGIN,
    RESULT_END,
    SANDBOX_IMAGE_PYGAME,
    SANDBOX_IMAGE_PYTHON,
    SandboxLimits,
    build_bundle,
    run_in_sandbox,
    split_result,
    truncate_tail,
    validate_env,
)


# ── Unit ───────────────────────────────────────────────────────

class TestEnvAllowlist:
    def test_rejects_credentials(self):
        for key in ("ARTIFACT_SECRET_KEY", "SESSION_REDIS_URL", "PATH", "HOME"):
            with pytest.raises(ValueError):
                validate_env({key: "x"})

    def test_accepts_adapter_vars(self):
        env = validate_env({"SDL_VIDEODRIVER": "dummy", "PYTHONHASHSEED": 0, "ABI_ACCEPTANCE_SEED": "1"})
        assert env == {"SDL_VIDEODRIVER": "dummy", "PYTHONHASHSEED": "0", "ABI_ACCEPTANCE_SEED": "1"}


class TestBundle:
    def _unpack(self, bundle):
        encoded = "".join(bundle[k] for k in sorted(bundle, key=lambda k: int(k.rsplit("_", 1)[1])))
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded)), mode="r:gz") as tar:
            return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}

    def test_roundtrip(self):
        files = {"main.py": b"print(1)", "pkg/mod.py": b"x = 2"}
        assert self._unpack(build_bundle(files)) == files

    def test_chunks_stay_under_linux_env_limit(self):
        import os
        files = {"big.bin": os.urandom(300 * 1024)}  # incompressible
        bundle = build_bundle(files)
        assert len(bundle) > 1
        assert all(len(v) < 128 * 1024 for v in bundle.values())
        assert self._unpack(bundle) == files

    @pytest.mark.parametrize("path", ["../escape.py", "/etc/passwd", "a/../../b.py", ".hidden", "a b.py"])
    def test_rejects_unsafe_paths(self, path):
        with pytest.raises(ValueError):
            build_bundle({path: b"x"})

    def test_rejects_oversized_bundle(self):
        import os
        with pytest.raises(ValueError):
            build_bundle({"big.bin": os.urandom(MAX_BUNDLE_BYTES)})


class TestResultFraming:
    def test_extracts_last_block(self):
        payload = base64.b64encode(b'{"ok": true}').decode()
        out = f"hello\n{RESULT_BEGIN}\n{payload}\n{RESULT_END}\n"
        stdout, result = split_result(out)
        assert stdout == "hello" and result == '{"ok": true}'

    def test_no_block(self):
        assert split_result("just output") == ("just output", None)

    def test_garbage_block_is_ignored(self):
        _, result = split_result(f"{RESULT_BEGIN}\nnot base64!!\n{RESULT_END}")
        assert result is None

    def test_truncate_keeps_tail(self):
        text, cut = truncate_tail("a" * 100 + "TRACEBACK", 20)
        assert cut and text.endswith("TRACEBACK")


# ── Docker (escape + functional) ───────────────────────────────

def _docker_ready(image):
    try:
        from abi_core.common.container_runtime import _get_docker_client
        _get_docker_client().images.get(image)
        return True
    except Exception:
        return False


docker_python = pytest.mark.skipif(not _docker_ready(SANDBOX_IMAGE_PYTHON),
                                   reason="Docker or abi-sandbox-python image not available")
docker_pygame = pytest.mark.skipif(not _docker_ready(SANDBOX_IMAGE_PYGAME),
                                   reason="Docker or abi-sandbox-pygame image not available")


async def _py(code, timeout_s=20, **kw):
    return await run_in_sandbox({"t.py": textwrap.dedent(code).encode()}, ["python", "t.py"],
                                limits=SandboxLimits(timeout_s=timeout_s), **kw)


def _leftovers():
    from abi_core.common.container_runtime import _get_docker_client
    return _get_docker_client().containers.list(all=True, filters={"label": "abi-sandbox=true"})


@docker_python
class TestEscape:
    @pytest.mark.asyncio
    async def test_env_and_privileges(self):
        r = await _py("""
            import os
            print(sorted(os.environ))
            print(open('/proc/self/status').read())
        """)
        assert r.exit_code == 0
        keys = set(eval(r.stdout.splitlines()[0]))
        # Exactly what the image defines; GPG_KEY is the public id of the
        # Python release-signing key (python:3.12-slim), not a secret.
        assert keys == {"GPG_KEY", "HOME", "HOSTNAME", "LANG", "PATH", "PYTHONDONTWRITEBYTECODE",
                        "PYTHONUNBUFFERED", "PYTHON_SHA256", "PYTHON_VERSION"}
        status = dict(l.split(":", 1) for l in r.stdout.splitlines()[1:] if ":" in l)
        assert status["Uid"].split()[0] == "10001"
        assert status["CapEff"].strip() == "0000000000000000"

    @pytest.mark.asyncio
    async def test_no_network(self):
        r = await _py("""
            import socket
            for host, port in [("abi-swarm-redis-stack", 6379), ("pypi.org", 443), ("1.1.1.1", 53)]:
                try:
                    socket.create_connection((host, port), timeout=3).close(); print("CONNECTED", host)
                except Exception:
                    pass
        """)
        assert r.exit_code == 0 and "CONNECTED" not in r.stdout

    @pytest.mark.asyncio
    async def test_fork_bomb_contained(self):
        r = await _py("""
            import os, time
            while True:
                try:
                    if os.fork() == 0:
                        time.sleep(60); os._exit(0)
                except OSError:
                    print("fork refused"); break
        """, timeout_s=15)
        assert "fork refused" in r.stdout

    @pytest.mark.asyncio
    async def test_memory_limit(self):
        r = await _py("chunks = [bytearray(32 * 1024 * 1024) for _ in range(64)]")
        assert r.oom_killed or "MemoryError" in r.stderr

    @pytest.mark.asyncio
    async def test_disk_quota_and_readonly_root(self):
        r = await _py("""
            try:
                with open('/workspace/big', 'wb') as f:
                    for _ in range(100): f.write(b'0' * 1024 * 1024)
                print("WROTE workspace")
            except OSError:
                pass
            for p in ['/etc/evil', '/opt/abi-sandbox/entry.py']:
                try:
                    open(p, 'w').write('x'); print("WROTE", p)
                except OSError:
                    pass
        """)
        assert "WROTE" not in r.stdout

    @pytest.mark.asyncio
    async def test_timeout(self):
        r = await _py("import time; time.sleep(1000)", timeout_s=5)
        assert r.timed_out and r.duration_s < 20

    @pytest.mark.asyncio
    async def test_output_truncated(self):
        r = await _py("import sys\nfor _ in range(10*1024): sys.stdout.write('x'*1023+'\\n')")
        assert r.stdout_truncated and len(r.stdout.encode()) <= 64 * 1024 + 64

    @pytest.mark.asyncio
    async def test_oversized_result_discarded(self):
        r = await _py("open('.result.json','w').write('\"' + 'a'*(1024*1024) + '\"')")
        assert r.result_json is None and "too large" in r.stderr

    @pytest.mark.asyncio
    async def test_result_json_and_missing_package(self):
        r = await _py("import json; json.dump({'ok': True}, open('.result.json', 'w'))")
        assert r.ok and json.loads(r.result_json) == {"ok": True}
        r = await _py("import flask")
        assert r.exit_code != 0 and "ModuleNotFoundError" in r.stderr

    def test_no_leftover_containers(self):
        assert _leftovers() == []


@docker_pygame
class TestPygameHeadless:
    @pytest.mark.asyncio
    async def test_game_loop_runs_and_crash_is_reported(self):
        sdl = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
        loop = textwrap.dedent("""
            import pygame
            pygame.init(); screen = pygame.display.set_mode((100, 100))
            frames = 0
            while True:
                pygame.event.get(); screen.fill((0, 0, 0)); pygame.display.flip(); frames += 1
                if CRASH and frames == 30:
                    len(object())
        """)
        ok = await run_in_sandbox({"g.py": ("CRASH = False\n" + loop).encode()}, ["python", "g.py"],
                                  image=SANDBOX_IMAGE_PYGAME, env=sdl, limits=SandboxLimits(timeout_s=5))
        assert ok.timed_out and "Traceback" not in ok.stderr
        bad = await run_in_sandbox({"g.py": ("CRASH = True\n" + loop).encode()}, ["python", "g.py"],
                                   image=SANDBOX_IMAGE_PYGAME, env=sdl, limits=SandboxLimits(timeout_s=5))
        assert bad.exit_code not in (0, None) and "has no len()" in bad.stderr
