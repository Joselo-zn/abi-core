# MCP Transport Flow Diagrams

## SSE Transport Flow

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant SSE as SSE Endpoint<br/>/sse
    participant Server as MCP Server
    participant Agent as Agent Service

    Client->>SSE: Connect (HTTP GET)
    SSE-->>Client: 200 OK (text/event-stream)
    
    Note over Client,SSE: Long-lived connection established
    
    Client->>SSE: Initialize Session
    SSE->>Server: Process Initialize
    Server-->>SSE: Session Ready
    SSE-->>Client: Session Initialized
    
    Client->>SSE: find_agent(query)
    SSE->>Server: Process Tool Call
    Server->>Agent: Search Agent Cards
    Agent-->>Server: Agent Found
    Server-->>SSE: Tool Result
    SSE-->>Client: Stream Response
    
    Note over Client,SSE: Unidirectional streaming
    
    Client->>SSE: Close Connection
    SSE-->>Client: Connection Closed
```

## Streamable HTTP Transport Flow

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant HTTP as HTTP Endpoint<br/>/mcp
    participant Server as MCP Server
    participant Agent as Agent Service

    Client->>HTTP: POST /mcp (Initialize)
    HTTP->>Server: Process Initialize
    Server-->>HTTP: Session Ready
    HTTP-->>Client: 200 OK (Session ID)
    
    Note over Client,HTTP: Bidirectional streaming
    
    Client->>HTTP: POST /mcp (find_agent)
    HTTP->>Server: Process Tool Call
    Server->>Agent: Search Agent Cards
    Agent-->>Server: Agent Found
    Server-->>HTTP: Tool Result
    HTTP-->>Client: Stream Response
    
    Client->>HTTP: POST /mcp (recommend_agents)
    HTTP->>Server: Process Tool Call
    Server->>Agent: Analyze Requirements
    Agent-->>Server: Recommendations
    Server-->>HTTP: Tool Result
    HTTP-->>Client: Stream Response
    
    Note over Client,HTTP: Multiple requests in session
    
    Client->>HTTP: POST /mcp (Close)
    HTTP-->>Client: 200 OK
```

## Transport Selection Logic

```mermaid
flowchart TD
    Start([Client Initialization]) --> CheckTransport{Check Transport<br/>Parameter}
    
    CheckTransport -->|transport='sse'| SSEPath[SSE Transport Path]
    CheckTransport -->|transport='streamable-http'| HTTPPath[HTTP Transport Path]
    CheckTransport -->|invalid| Error[Raise ValueError]
    
    SSEPath --> SSEConnect[Connect to /sse]
    SSEConnect --> SSEStream[Establish SSE Stream]
    SSEStream --> SSESession[Create ClientSession]
    SSESession --> SSEInit[Initialize Session]
    SSEInit --> Ready1([Ready for Operations])
    
    HTTPPath --> HTTPConnect[Connect to /mcp]
    HTTPConnect --> HTTPStream[Establish HTTP Stream]
    HTTPStream --> HTTPSession[Create ClientSession]
    HTTPSession --> HTTPInit[Initialize Session]
    HTTPInit --> Ready2([Ready for Operations])
    
    Error --> End([Error: Unsupported Transport])
    
    style SSEPath fill:#e3f2fd
    style HTTPPath fill:#f3e5f5
    style Error fill:#ffebee
    style Ready1 fill:#c8e6c9
    style Ready2 fill:#c8e6c9
```

## Environment Configuration Flow

```mermaid
flowchart LR
    subgraph Environment
        ENV1[MCP_TRANSPORT=sse]
        ENV2[MCP_HOST=localhost]
        ENV3[MCP_PORT=10100]
    end
    
    subgraph Application
        Config[get_mcp_server_config]
        Client[MCP Client]
    end
    
    subgraph Transport Layer
        SSE[SSE Client<br/>http://localhost:10100/sse]
        HTTP[HTTP Client<br/>http://localhost:10100/mcp]
    end
    
    ENV1 --> Config
    ENV2 --> Config
    ENV3 --> Config
    
    Config -->|transport='sse'| Client
    Client -->|SSE| SSE
    
    Config -.->|transport='streamable-http'| Client
    Client -.->|HTTP| HTTP
    
    style ENV1 fill:#fff3e0
    style ENV2 fill:#fff3e0
    style ENV3 fill:#fff3e0
    style SSE fill:#e3f2fd
    style HTTP fill:#f3e5f5
```

## Agent Communication Pattern

```mermaid
flowchart TD
    subgraph Orchestrator Agent
        OConfig[Config:<br/>MCP_TRANSPORT=sse]
        OClient[MCP Client]
    end
    
    subgraph Planner Agent
        PConfig[Config:<br/>MCP_TRANSPORT=sse]
        PClient[MCP Client]
    end
    
    subgraph Semantic Layer
        MCP[MCP Server]
        SSE[/sse endpoint]
        HTTP[/mcp endpoint]
    end
    
    subgraph Agent Registry
        Cards[(Agent Cards)]
        Weaviate[(Weaviate<br/>Vector DB)]
    end
    
    OConfig --> OClient
    PConfig --> PClient
    
    OClient -->|SSE| SSE
    PClient -->|SSE| SSE
    
    SSE --> MCP
    HTTP -.-> MCP
    
    MCP --> Cards
    MCP --> Weaviate
    
    style OConfig fill:#e8f5e8
    style PConfig fill:#e8f5e8
    style SSE fill:#e3f2fd
    style HTTP fill:#f3e5f5
    style Cards fill:#fff3e0
    style Weaviate fill:#fff3e0
```

## Performance Comparison

```mermaid
graph LR
    subgraph SSE Performance
        SSE1[Latency: 10-50ms]
        SSE2[Throughput: Good]
        SSE3[Memory: Low]
        SSE4[Direction: Unidirectional]
    end
    
    subgraph HTTP Performance
        HTTP1[Latency: 5-20ms]
        HTTP2[Throughput: Better]
        HTTP3[Memory: Medium]
        HTTP4[Direction: Bidirectional]
    end
    
    SSE1 -.->|vs| HTTP1
    SSE2 -.->|vs| HTTP2
    SSE3 -.->|vs| HTTP3
    SSE4 -.->|vs| HTTP4
    
    style SSE1 fill:#e3f2fd
    style SSE2 fill:#e3f2fd
    style SSE3 fill:#e3f2fd
    style SSE4 fill:#e3f2fd
    style HTTP1 fill:#f3e5f5
    style HTTP2 fill:#f3e5f5
    style HTTP3 fill:#f3e5f5
    style HTTP4 fill:#f3e5f5
```

## Error Handling Flow

```mermaid
flowchart TD
    Start([Client Request]) --> Try{Try Transport}
    
    Try -->|SSE| SSEAttempt[Attempt SSE Connection]
    Try -->|HTTP| HTTPAttempt[Attempt HTTP Connection]
    
    SSEAttempt --> SSECheck{Connection OK?}
    HTTPAttempt --> HTTPCheck{Connection OK?}
    
    SSECheck -->|Yes| SSESuccess[SSE Session Active]
    SSECheck -->|No| SSEError[Log SSE Error]
    
    HTTPCheck -->|Yes| HTTPSuccess[HTTP Session Active]
    HTTPCheck -->|No| HTTPError[Log HTTP Error]
    
    SSEError --> Fallback{Fallback Available?}
    HTTPError --> Fallback
    
    Fallback -->|Yes| Try
    Fallback -->|No| Failed([Connection Failed])
    
    SSESuccess --> Operations[Execute Operations]
    HTTPSuccess --> Operations
    
    Operations --> Complete([Success])
    
    style SSESuccess fill:#c8e6c9
    style HTTPSuccess fill:#c8e6c9
    style Complete fill:#c8e6c9
    style SSEError fill:#ffebee
    style HTTPError fill:#ffebee
    style Failed fill:#ffebee
```

## Migration Path

```mermaid
flowchart LR
    subgraph v1.5.10 and Earlier
        Old[SSE Only<br/>transport='sse']
    end
    
    subgraph v1.5.11+
        New1[SSE Support<br/>transport='sse'<br/>✓ Default]
        New2[HTTP Support<br/>transport='streamable-http'<br/>✓ New Option]
    end
    
    subgraph Migration
        M1[No Code Changes<br/>Required]
        M2[Optional: Update<br/>Environment Variables]
        M3[Optional: Test<br/>Both Transports]
    end
    
    Old -->|Upgrade| New1
    Old -.->|Optional| New2
    
    New1 --> M1
    New2 --> M2
    M2 --> M3
    
    style Old fill:#e0e0e0
    style New1 fill:#c8e6c9
    style New2 fill:#f3e5f5
    style M1 fill:#fff3e0
    style M2 fill:#fff3e0
    style M3 fill:#fff3e0
```
