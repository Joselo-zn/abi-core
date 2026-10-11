"""Write Chainlit's default translations with ABI's step-header overrides.

The run step's name already reads as an action ("Diseñando el plan · 23s"),
so Chainlit's "Using"/"Used" prefix is blanked. Only files that don't exist
yet are written — a project's own translations are never overwritten. Run by
the Dockerfile `abi-core add chainlit` generates:

    python -m abi_core.ui.translations .chainlit/translations

See .abi/specs/not-implemented/ux/chainlit-run-progress-indicator.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def write_default_translations(dest_dir: str | Path) -> list[Path]:
    """Create every missing ``<lang>.json`` in *dest_dir* from Chainlit's
    bundled translations, with ``chat.messages.status.using/used`` set to
    "". Returns the files written."""
    import chainlit

    src_dir = Path(chainlit.__file__).parent / "translations"
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for src in sorted(src_dir.glob("*.json")):
        dest = dest_dir / src.name
        if dest.exists():
            continue
        translation = json.loads(src.read_text(encoding="utf-8"))
        status = translation.get("chat", {}).get("messages", {}).get("status")
        if isinstance(status, dict):
            status["using"] = ""
            status["used"] = ""
        dest.write_text(json.dumps(translation, indent=4, ensure_ascii=False), encoding="utf-8")
        written.append(dest)
    return written


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ".chainlit/translations"
    for path in write_default_translations(target):
        print(f"Created {path}")
