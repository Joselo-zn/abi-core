# Personal Research & Deep Search

Many agentic systems write research the way a hurried student writes an essay: confident, fluent, and citing things nobody can find. Ask one about a topic and you get something like this — an illustration, not any real product:

```
You:  What is the Model Context Protocol, and who created it?
Bot:  MCP is a protocol released by OpenAI in 2023 to let models share memory
      across sessions [1]. As the specification states, "MCP guarantees
      end-to-end encryption of all model context" [2].
You:  Where's that quote from?
Bot:  From source [2], the MCP whitepaper.
You:  I only gave you one link.
```

Wrong company, wrong year, a quote nobody wrote, and a source that doesn't exist.

I'm ABI, and in research the model does the reading and the writing — and code checks its homework. Code fetches your sources, all at once; the model takes notes on each one; every quote it brings back is compared word for word with the page, and the ones that aren't there are dropped; every `[n]` in the report must point at a source that was actually read. A dead link is reported, not invented around. Here's an excerpt from a real run:

```
The Model Context Protocol (MCP) is an open standard and open-source framework developed by
Anthropic, introduced in November 2024 [1]. It was created by engineers David Soria Parra and
Justin Spahr-Summers at Anthropic [1]. ... MCP is compared to a USB-C port for AI applications,
offering a standardized way to connect to external systems [2]. ...

Sources
[1] Model Context Protocol - Wikipedia — https://en.wikipedia.org/wiki/Model_Context_Protocol
    > The protocol was created at Anthropic by engineers David Soria Parra and Justin Spahr-Summers.
    > Client and server communicate using the JSON-RPC 2.0 messages.
[2] What is the Model Context Protocol (MCP)? — https://modelcontextprotocol.io/docs/getting-started/intro
    > Think of MCP like a USB-C port for AI applications. ...
[3] https://this-link-does-not-exist.example/mcp — couldn't read it (ConnectError)

Quotes checked against the sources: 5 found word for word, 4 dropped.
```

Four of the nine quotes the model offered weren't in the pages. You never saw them.

It takes about twenty minutes to build.

## What you'll build

One agent, `researcher`. You send a question and the links to read:

```
message ──▶ links → sources, the rest → the question (code)
        ──▶ fetch every source in parallel, strip the page to text (code)
        ──▶ notes per source: key points + quotes (model, fixed shape)
        ──▶ keep only quotes found word for word in the page (code)
        ──▶ report from the notes, every claim cited [n] (model)
        ──▶ every [n] must be a source that was read (code)
        ──▶ report + sources + the verified quotes
```

ABI features on this page: `asyncio.gather` over steps for parallel fetching and reading, `invoke_structured`, and status updates while it works.

## Step 1: Create the project and the agent

```bash
abi-core create project --name research
cd research
```

Answer `n` to the semantic layer and to Guardian, and press Enter for the rest. Then:

```bash
abi-core add agent --name researcher \
  --description "Reads the sources you give it and writes a cited report, checking every quote" \
  --with-web-interface
```

When it asks for tasks/skills, type `research`. Press Enter for the URL.

## Step 2: What the model may note

Replace the contents of `agents/researcher/models.py`:

```python
"""What the model may hand back about one source."""

from typing import List

from pydantic import BaseModel, Field


class SourceNotes(BaseModel):
    key_points: List[str] = Field(
        description="Up to 5 short points from the source that answer the question; empty if it doesn't"
    )
    quotes: List[str] = Field(description="Up to 3 sentences copied word for word from the source that back those points")
```

An earlier version also asked the model whether each source was "relevant". It marked the official MCP introduction as irrelevant to a question about MCP. Now a source counts if the model found something in it that answers the question — one judgment fewer.

## Step 3: The prompts

Create `agents/researcher/prompts.py`:

```python
READ_PROMPT = """Read this source and note what it says about the question.
Quotes must be copied exactly, word for word, from the source text.

Question: {question}

Source [{n}] {title}:
{text}"""

REPORT_PROMPT = """Write a short research report (at most 250 words) that answers the question,
using ONLY the notes below. Cite every claim with the source number in brackets, like [1].
If the sources disagree or don't cover part of the question, say so.

Question: {question}

Notes:
{notes}"""
```

## Step 4: The steps

Replace the contents of `agents/researcher/steps.py`:

```python
import asyncio
import json
import re

import httpx
from bs4 import BeautifulSoup

from app import agent
from config import config
from abi_core.agent.llm_provider import invoke, invoke_structured
from models import SourceNotes
from prompts import READ_PROMPT, REPORT_PROMPT

MAX_SOURCES = 5
MAX_CHARS = 12_000  # what each source can put in front of the model


def _clean(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    return title, re.sub(r"\s+", " ", soup.get_text(" ")).strip()


async def _fetch(client, url):
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        title, text = _clean(resp.text)
        return {"url": url, "title": title or url, "text": text[:MAX_CHARS], "error": None}
    except Exception as e:
        return {"url": url, "title": url, "text": "", "error": type(e).__name__}


@agent.step(name="fetch_sources")
async def fetch_sources(urls):
    """Download every source at the same time. A dead link is a result, not a crash."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                 headers={"User-Agent": "abi-research-demo/1.0"}) as client:
        return {"sources": await asyncio.gather(*[_fetch(client, u) for u in urls[:MAX_SOURCES]])}


@agent.step(name="read_source")
async def read_source(question, n, source):
    notes = await invoke_structured(config.LLM_CONFIG, READ_PROMPT.format(
        question=question, n=n, title=source["title"], text=source["text"],
    ), SourceNotes)
    return notes.model_dump()


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘]", "", text)).strip().lower()


@agent.step(name="verify_quotes")
async def verify_quotes(notes, source_text):
    """A quote stays only if it really is in the source. Plain string matching — no model."""
    haystack = _norm(source_text)
    kept = [q for q in notes["quotes"] if len(q) > 20 and _norm(q) in haystack]
    return {"verified": kept, "dropped": len(notes["quotes"]) - len(kept)}


@agent.step(name="write_report")
async def write_report(question, notes_by_source):
    reply = await invoke(config.LLM_CONFIG, REPORT_PROMPT.format(
        question=question, notes=json.dumps(notes_by_source, indent=1, ensure_ascii=False),
    ))
    return {"report": reply}


@agent.step(name="check_citations")
async def check_citations(report, valid_numbers):
    """Every [n] must point at a source we actually read."""
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", report)}
    return {"unknown": sorted(cited - set(valid_numbers)), "uncited": not cited}
```

`verify_quotes` is the whole trick: a quote survives only if, after ignoring quotation marks and spacing, it appears in the page text. `check_citations` does the same for the numbers in brackets.

## Step 5: The task

Replace the contents of `agents/researcher/tasks.py`:

```python
import asyncio
import re

from app import agent
from abi_core.agent.agent_response import AgentResponse

HOW_TO = "Send a question and the links to read, e.g. \"What is X? https://... https://...\""


@agent.task(name="research", task_id="task-research")
async def research(query, context_id=None):
    # 1. Split the message: links are sources, the rest is the question (code).
    urls = re.findall(r"https?://\S+", query)
    question = re.sub(r"https?://\S+", "", query).strip()
    if not urls or not question:
        yield AgentResponse.text(HOW_TO)
        return

    # 2. Fetch every source at once.
    yield AgentResponse.status(f"Reading {len(urls)} source(s)...")
    sources = (await agent.execute_step("fetch_sources", urls=urls))["sources"]
    readable = [(n, s) for n, s in enumerate(sources, 1) if s["text"]]
    if not readable:
        yield AgentResponse.text("I couldn't read any of those links.")
        return

    # 3. The model takes notes on each source; code keeps only quotes that are really there.
    yield AgentResponse.status("Taking notes...")
    notes = await asyncio.gather(*[
        agent.execute_step("read_source", question=question, n=n, source=s) for n, s in readable
    ])
    notes_by_source, dropped = {}, 0
    for (n, s), note in zip(readable, notes):
        checked = await agent.execute_step("verify_quotes", notes=note, source_text=s["text"])
        dropped += checked["dropped"]
        if note["key_points"]:  # a source counts if it says something about the question
            notes_by_source[n] = {"title": s["title"], "key_points": note["key_points"],
                                  "quotes": checked["verified"]}
    if not notes_by_source:
        yield AgentResponse.text("None of the sources I could read answers that question.")
        return

    # 4. The report, from the notes only; code checks every citation.
    yield AgentResponse.status("Writing the report...")
    report = (await agent.execute_step("write_report", question=question, notes_by_source=notes_by_source))["report"]
    citations = await agent.execute_step("check_citations", report=report, valid_numbers=list(notes_by_source))

    warnings = []
    if citations["unknown"]:
        warnings.append(f"⚠️ The report cites sources that weren't used: {citations['unknown']}.")
    if citations["uncited"]:
        warnings.append("⚠️ The report has no citations — treat it as unsupported.")

    lines = []
    for n, s in enumerate(sources, 1):
        if s["error"]:
            lines.append(f"[{n}] {s['url']} — couldn't read it ({s['error']})")
        elif n in notes_by_source:
            lines.append(f"[{n}] {s['title']} — {s['url']}")
            lines += [f"    > {q}" for q in notes_by_source[n]["quotes"]]
        else:
            lines.append(f"[{n}] {s['title']} — {s['url']} (not relevant)")
    kept = sum(len(v["quotes"]) for v in notes_by_source.values())
    yield AgentResponse.text(
        report + ("\n\n" + "\n".join(warnings) if warnings else "")
        + "\n\n**Sources**\n" + "\n".join(lines)
        + f"\n\n_Quotes checked against the sources: {kept} found word for word, {dropped} dropped._"
    )
```

## Step 6: Run it

The agent needs internet access to read the links — the default Docker network has it. In `compose.yaml`, add to the `environment` of the `research-researcher` service:

```yaml
      - 'LLM_EXTRA_PARAMS={"reasoning": false}'
```

Then:

```bash
abi-core add chainlit
docker compose up ollama -d
docker exec ollama ollama pull qwen3:latest
abi-core run --build
```

## Step 7: Use it

Open **http://localhost:8500** and send a question followed by two or three links. The progress step shows each stage — reading, taking notes, writing — and the answer ends with the sources and the quotes that survived the check. Add a broken link on purpose.

### Or from a script

Save this as `ask.py` in the project folder:

```python
import asyncio
from abi_core.client import AgentStreamClient

QUESTION = (
    "What is the Model Context Protocol, who created it, and how do clients talk to servers? "
    "https://en.wikipedia.org/wiki/Model_Context_Protocol "
    "https://modelcontextprotocol.io/docs/getting-started/intro "
    "https://this-link-does-not-exist.example/mcp"
)


async def main():
    client = AgentStreamClient("http://localhost:8002")
    async for event in client.stream(QUESTION):
        if event.get("response_type") == "status":
            print("…", event.get("content"))
        elif event.get("is_task_completed") or event.get("response_type") == "error":
            print(event.get("content"))

asyncio.run(main())
```

```bash
python ask.py
```

On a laptop CPU with `qwen3:latest`, this took two and a half to five minutes: each source puts up to 12,000 characters in front of the model, and a single local model reads them one after another. A GPU or a cloud model makes it a matter of seconds.

## What happened

1. **The message was split by code:** three links, one question.
2. **All three links were fetched at once.** Two returned pages; the third doesn't exist, and was recorded as a `ConnectError` instead of stopping the run.
3. **The model took notes on each page,** in a fixed shape: key points and quotes.
4. **Code checked every quote against its page.** Five were there word for word. Four weren't — paraphrases presented as quotes — and were dropped before the report was written.
5. **The model wrote the report from the notes,** citing `[1]` and `[2]`. Code confirmed both numbers belong to sources that were read.

What the model never did: choose what to read, decide that a quote was real, or cite a source that wasn't there.

## Before you rely on it

- **Add search.** This page reads the links you give it. To find sources too, call a search API from a step, and keep the same checks on whatever comes back.
- **Handle long documents.** Pages are cut at 12,000 characters. For long reports or PDFs, split them into chunks and take notes per chunk, or use a model with a larger context.
- **Deliver a file.** Turn the report into a PDF with `write_pdf` and share it through the [Artifact Store](../production/05-artifact-store.md).
- **Respect the sites you read.** Follow each site's terms and `robots.txt`, identify your client honestly (the `User-Agent` header), and cache what you fetch.
- **Remember: a real quote isn't a true claim.** The check proves the sentence is on the page — not that the page is right. The sources list is there so a person can judge them.

## Next

👉 Back to [Use Cases](index.md)
