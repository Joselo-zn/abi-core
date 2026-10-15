# MCP Transports

Agents talk to the Semantic Layer over [MCP](https://modelcontextprotocol.io) — every `find_agent`, every `MCPToolkit` call. MCP defines how those messages travel, and ABI-Core supports two ways:

| Transport | Status in MCP | In ABI-Core |
|-----------|---------------|-------------|
| **Streamable HTTP** | The standard HTTP transport since the 2025-03-26 specification | Default |
| **HTTP+SSE** | Replaced by Streamable HTTP in 2025-03-26; the 2025-06-18 specification calls it deprecated | Still accepted, for compatibility only |

(MCP's other standard transport, stdio, is for local processes and isn't used between ABI services.)

Use Streamable HTTP. Choose SSE only to talk to an older MCP server that has nothing else.

## Streamable HTTP (default)

Every message is an HTTP `POST` to one endpoint, `/mcp`. The server answers each request with a single response or a stream of events, and identifies the session with a header, so one session carries any number of calls:

```
Agent (MCP client)                         Semantic Layer (MCP server)
      │                                                │
      ├── POST /mcp   initialize ─────────────────────▶│
      │◀──────────────────── session id ──────────────┤
      │                                                │
      ├── POST /mcp   tools/call find_agent ──────────▶│
      │◀──────────────────── result ──────────────────┤
      │                                                │
      ├── POST /mcp   tools/call recommend_agents ────▶│
      │◀──────────────────── result ──────────────────┤
```

## HTTP+SSE (deprecated)

The client keeps a long-lived `GET /sse` connection open to receive messages, and sends its own messages on a separate endpoint the server announces on that connection. Two channels instead of one, and a connection that must stay open for the whole session:

```
Agent (MCP client)                         Semantic Layer (MCP server)
      │                                                │
      ├── GET /sse ───────────────────────────────────▶│  (stays open)
      │◀──────────────── endpoint for messages ────────┤
      │                                                │
      ├── POST <endpoint>   tools/call find_agent ────▶│
      │◀──────────── result, on the /sse stream ───────┤
```

## Choosing the transport

Both sides have to agree, and each reads its own variable:

| Side | Variable | Default |
|------|----------|---------|
| Agents (MCP clients: `MCPToolkit`, the semantic tools) | `MCP_TRANSPORT` | `streamable-http` |
| Semantic Layer (MCP server) | `SEMANTIC_LAYER_TRANSPORT` | `streamable-http` |

With both unset, everything uses Streamable HTTP on `http://<semantic-layer-host>:10100/mcp`. To fall back to SSE, set **both** to `sse` — an agent on `sse` talking to a server on `streamable-http` (or the other way around) can't open a session. Any other value is rejected with a `ValueError`.

See [Environment Variables → Semantic Layer](environment-variables.md#semantic-layer).
