"""ABI sandbox entrypoint — runs inside every sandbox container.

Contract with abi_core.common.sandbox (the runtime side):
  1. The files to run arrive as a gzip'd tar, base64-encoded and split
     across ABI_SANDBOX_BUNDLE_0..N environment variables (a single env
     string is capped at 128 KiB by Linux; Cloud Run Jobs can only
     override env/args per execution, not volumes — one contract for both
     backends). They are extracted into /workspace (a size-limited tmpfs).
  2. The command (argv) is chosen by the runtime's domain adapter, never by
     an LLM, and runs in /workspace without the bundle variables.
  3. If the command leaves /workspace/.result.json, it is printed on stdout
     between marker lines after the command exits. Like everything coming
     out of a sandbox, it is untrusted data: the caller parses it, never
     executes or trusts it.
  4. The exit code is the command's exit code.

No network, no credentials, non-root, read-only root filesystem — all
enforced by the runtime, not by this script.
"""

import base64
import io
import os
import subprocess
import sys
import tarfile

WORKSPACE = "/workspace"
RESULT_FILE = os.path.join(WORKSPACE, ".result.json")
RESULT_BEGIN = "<<<ABI_SANDBOX_RESULT_BEGIN>>>"
RESULT_END = "<<<ABI_SANDBOX_RESULT_END>>>"
MAX_RESULT_BYTES = int(os.environ.pop("ABI_SANDBOX_MAX_RESULT_BYTES", str(256 * 1024)))


def _take_bundle() -> bytes:
    chunks = []
    i = 0
    while True:
        part = os.environ.pop(f"ABI_SANDBOX_BUNDLE_{i}", None)
        if part is None:
            break
        chunks.append(part)
        i += 1
    return base64.b64decode("".join(chunks)) if chunks else b""


def main() -> int:
    bundle = _take_bundle()
    if bundle:
        with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as tar:
            # "data" filter: no absolute paths, no "..", no links outside,
            # no device files — the tar is built by the runtime, but the
            # file names inside come from generated deliverables.
            tar.extractall(WORKSPACE, filter="data")

    if len(sys.argv) < 2:
        print("abi-sandbox: no command given", file=sys.stderr)
        return 2

    try:
        code = subprocess.call(sys.argv[1:], cwd=WORKSPACE)
    except FileNotFoundError as e:
        print(f"abi-sandbox: command not found: {e}", file=sys.stderr)
        code = 127

    if os.path.isfile(RESULT_FILE):
        size = os.path.getsize(RESULT_FILE)
        if size > MAX_RESULT_BYTES:
            print(f"abi-sandbox: .result.json too large ({size} bytes), discarded", file=sys.stderr)
        else:
            with open(RESULT_FILE, "rb") as f:
                payload = base64.b64encode(f.read()).decode()
            sys.stdout.flush()
            print(f"\n{RESULT_BEGIN}\n{payload}\n{RESULT_END}", flush=True)

    return code


if __name__ == "__main__":
    sys.exit(main())
