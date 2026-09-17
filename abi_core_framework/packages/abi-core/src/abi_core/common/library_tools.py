"""
Library Tools — Dynamic tool resolution for zombie agents.

Provides base tools (shell, file write) and resolves additional tools
from the semantic layer based on the zombie's assigned capabilities.

Usage:
    from abi_core.common.library_tools import zombie_tools
    tools = zombie_tools(zombie_id, workspace="/app/workspace")
"""

import os
import subprocess
from typing import List, Optional

from langchain_core.tools import tool as langchain_tool

from abi_core.common.utils import abi_logging


# ── Base Tools (always available to zombies) ───────────────────

WORKSPACE = os.getenv("WORKSPACE", "/app/workspace")


@langchain_tool
def write_file(filename: str, content: str) -> str:
    """Write content to a file in the workspace.

    Args:
        filename: Name of the file to create (e.g. 'hello.sh', 'main.py').
        content: The full content to write to the file.

    Returns:
        Confirmation message with the file path.
    """
    try:
        os.makedirs(WORKSPACE, exist_ok=True)
        filepath = os.path.join(WORKSPACE, filename)

        with open(filepath, "w") as f:
            f.write(content)

        abi_logging(f"[📝] File written: {filepath} ({len(content)} bytes)")
        return f"File written: {filepath}"

    except Exception as e:
        abi_logging(f"[❌] File write error: {str(e)}")
        return f"Error writing file: {e}"


@langchain_tool
def read_file(filename: str) -> str:
    """Read the contents of a file from the workspace.

    Args:
        filename: Name of the file to read.

    Returns:
        The file contents as a string.
    """
    filepath = os.path.join(WORKSPACE, filename)
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"
    with open(filepath, "r") as f:
        return f.read()


@langchain_tool
def run_shell(command: str) -> str:
    """Execute a shell command in the workspace directory.

    Args:
        command: The shell command to execute.

    Returns:
        stdout + stderr output from the command.
    """
    abi_logging(f"[🐚] Shell: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=WORKSPACE,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error: {e}"


@langchain_tool
def list_files() -> str:
    """List all files in the workspace directory.

    Returns:
        Newline-separated list of filenames in the workspace.
    """
    os.makedirs(WORKSPACE, exist_ok=True)
    files = os.listdir(WORKSPACE)
    if not files:
        return "(workspace is empty)"
    return "\n".join(files)


# fpdf2's core "Helvetica" font only supports Latin-1 — plenty for Spanish
# accents (á, é, ñ, ¿, ¡...) but not "smart" typography LLMs commonly
# produce (curly quotes, en/em dashes, ellipsis character). Normalize those
# to their closest Latin-1/ASCII equivalent instead of crashing write_pdf.
_PDF_CHAR_REPLACEMENTS = {
    "‘": "'", "’": "'",  # ‘ ’
    "“": '"', "”": '"',  # “ ”
    "–": "-", "—": "-",  # – —
    "…": "...",  # …
    " ": " ",  # non-breaking space
}


def _sanitize_pdf_text(text: str) -> str:
    for char, replacement in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    # Final safety net: anything still outside Latin-1 becomes "?" instead
    # of crashing the PDF render.
    return text.encode("latin-1", errors="replace").decode("latin-1")


@langchain_tool
def write_pdf(filename: str, content: str) -> str:
    """Write text content to a PDF file in the workspace.

    Fixed, audited tool — renders `content` as plain paragraphs via fpdf2.
    No code execution: the only untrusted input is the text itself, never
    a command or script. See .abi/specs/planner-direct-tool-pdf.md.

    Args:
        filename: Name of the PDF file to create (e.g. 'itinerary.pdf').
        content: The full text content to render into the PDF.

    Returns:
        Confirmation message with the file path.
    """
    try:
        from fpdf import FPDF

        os.makedirs(WORKSPACE, exist_ok=True)
        filepath = os.path.join(WORKSPACE, filename)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, _sanitize_pdf_text(content))
        pdf.output(filepath)

        abi_logging(f"[📄] PDF written: {filepath} ({len(content)} chars)")
        return f"PDF written: {filepath}"

    except Exception as e:
        abi_logging(f"[❌] PDF write error: {str(e)}")
        return f"Error writing PDF: {e}"


# ── Base tools set ─────────────────────────────────────────────

BASE_TOOLS = [write_file, read_file, run_shell, list_files, write_pdf]


# ── Dynamic tool resolution ────────────────────────────────────

def zombie_tools(
    zombie_id: str = None,
    workspace: str = None,
    include_base: bool = True,
) -> List:
    """Resolve tools for a zombie agent.

    1. Always includes base tools (write_file, read_file, run_shell, list_files)
    2. Resolves additional library tools from the semantic layer (future)

    Args:
        zombie_id: Zombie agent identifier for semantic layer lookup.
        workspace: Override workspace directory.
        include_base: Include base tools (default True).

    Returns:
        List of LangChain tools ready for use.
    """
    global WORKSPACE
    if workspace:
        WORKSPACE = workspace

    tools = []

    if include_base:
        tools.extend(BASE_TOOLS)
        abi_logging(f"[🔧] Base tools loaded: {[t.name for t in BASE_TOOLS]}")

    # Future: resolve additional tools from semantic layer
    # if zombie_id:
    #     libs_tools = AbiGetLibsTools()
    #     zombie_libs = libs_tools.get(zombie_id)
    #     for tool_spec in zombie_libs:
    #         tool = _import_langchain_tool(tool_spec)
    #         if tool:
    #             tools.append(tool)

    abi_logging(f"[🔧] Total tools for zombie: {len(tools)}")
    return tools
