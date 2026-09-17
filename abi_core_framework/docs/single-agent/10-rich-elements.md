# Rich Elements — Images, Files, QR Codes, and Custom Cards

```{note}
**Alpha.** `AgentResponse.element()` is under active development. Built-in
element types (image, file, pdf, audio, video, text, dataframe, qr) are
stable; custom `.jsx` elements are new.
```

So far your agent's responses have been text and structured data (`AgentResponse.text`/`.result`). Sometimes that's not the best way to show something — a generated chart is more useful as an image than a wall of numbers, and a download link is easier to act on as a QR code than a URL someone has to copy on their phone. `AgentResponse.element()` lets your agent send those directly, and a Chainlit-based UI (like `abi-core ui chainlit`) renders them inline.

## Built-in element types

```python
from abi_core.agent.agent_response import AgentResponse

@agent.task(name="report")
async def report(query):
    yield AgentResponse.status("Generating report...")
    # ... do the work, upload a file, get a public URL back ...
    yield AgentResponse.element("image", {"url": chart_url}, name="Sales chart")
    yield AgentResponse.text("Here's your report.")
```

| `element_type` | `props` | Notes |
|---|---|---|
| `image` | `url` or `path` or `content` | Prefer `url` for anything already uploaded — see below |
| `file` | `url` or `path` or `content` | Generic file download |
| `pdf` | `url` or `path` or `content` | |
| `audio` | `url` or `path` or `content` | |
| `video` | `url` or `path` or `content` | |
| `text` | `content`, optional `language` | A text block rendered as its own element, not inline in the message |
| `dataframe` | anything `pandas.DataFrame(**props)` accepts | Requires `pandas` installed where the UI runs |
| `qr` | `data` (the string/URL to encode) | Generates the QR image server-side — your agent never needs a QR library |

An agent can send zero, one, or several elements before its final `text`/`result` — the UI collects them and attaches them to the message they belong with.

## Prefer a URL over inline bytes

For anything binary (`image`/`file`/`pdf`/`audio`/`video`), pass a `url` your agent already has — typically from [the Artifact Store](../production/05-artifact-store.md) — instead of embedding raw content in the response:

```python
from abi_core.common.artifact_store import generate_download_urls

await generate_download_urls(artifacts)
yield AgentResponse.element("image", {"url": artifacts[0]["download_url"]}, name=artifacts[0]["filename"])
```

Embedding bytes directly works too (`content=` in `props`), but it inflates every message that carries it — fine for something genuinely small (a QR code), not for a report-sized PDF.

## QR codes

```python
yield AgentResponse.element("qr", {"data": download_url}, name=f"QR — {filename}")
```

The UI renders it as a plain `image` element — your agent doesn't need the `qrcode` package, only whatever process actually renders it does (already included in the `ui` extra: `pip install "abi-core-ai[ui]"`).

## Custom elements

For anything the built-in types don't cover — a status card, an embedded map — `abi-core` ships a couple of ready-made `.jsx` components and auto-installs them wherever `abi_core.ui.chainlit_app` runs, no project setup needed:

```python
yield AgentResponse.element("InfoCard", {
    "title": "Fix Authentication Bug",
    "status": "in-progress",
    "progress": 0.6,          # 0-1, rendered as a progress bar
    "assignee": "Sarah Chen",
    "date": "2026-01-15",
    "tags": ["security", "high-priority"],
})
```

```python
yield AgentResponse.element("MapEmbed", {
    "embedUrl": f"https://www.google.com/maps/embed/v1/directions?origin={a}&destination={b}&key={api_key}",
})
```

`element_type` is the component's name — `abi-core` looks for a matching `.jsx`, whether it's one of the bundled ones or your own. To add a project-specific element, drop a `.jsx` file (JSX only, no TSX) into `public/elements/<YourName>.jsx` in your Chainlit UI project — same convention Chainlit itself uses. Props are injected globally into the component's scope (`props.title`, not a function argument). Only a fixed set of libraries are available inside a custom element: React, Tailwind, shadcn UI components, Lucide icons, Recoil, React Hook Form, Zod, Sonner — no other npm imports. Plain HTML tags like `<iframe>` aren't restricted, which is how `MapEmbed` embeds a live map without needing a maps SDK.

## Next step

👉 [Testing Agents](05-testing-agents.md)
