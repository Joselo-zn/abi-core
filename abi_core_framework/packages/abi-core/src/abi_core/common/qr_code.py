"""
QR code generation — used by ``AgentResponse.element("qr", {"data": ...})``.

Lives here (not in the agent/orchestrator packages) so any renderer of
AgentResponse elements can reuse it, and agents never need to depend on
``qrcode`` themselves — only whatever process actually renders the element
(e.g. abi_core.ui.chainlit_app) does. See
.abi/specs/agent-rich-elements.md.
"""

import io


def generate_qr_png(data: str) -> bytes:
    """Render ``data`` (typically a URL) as a QR code PNG.

    Args:
        data: The text/URL to encode.

    Returns:
        PNG image bytes.
    """
    import qrcode

    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
