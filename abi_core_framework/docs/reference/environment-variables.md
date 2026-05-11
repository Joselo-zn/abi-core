# Environment Variables

All variables are set in `compose.yaml` per service. Agents read them via `config/config.py`.

## Agent configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `qwen2.5:3b` | LLM model name |
| `OLLAMA_HOST` | `http://<project>-ollama:11434` | Ollama server URL |
| `LLM_PROVIDER` | `ollama` | Provider: ollama, openai, gemini, grok, anthropic, bedrock, azure |
| `LLM_API_KEY` | — | API key for cloud providers |
| `LLM_TEMPERATURE` | `0.1` | LLM temperature |
| `AGENT_PORT` | auto-assigned | A2A protocol port |
| `WEB_INTERFACE_PORT` | auto-assigned | HTTP/SSE port (if web interface enabled) |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |

## Semantic Layer

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMANTIC_LAYER_HOST` | `http://<project>-semantic-layer:10100` | Semantic Layer URL |
| `MCP_HOST` | `<project>-semantic-layer` | MCP server hostname |
| `MCP_PORT` | `10100` | MCP server port |
| `MCP_TRANSPORT` | `streamable-http` | Transport: streamable-http, sse |
| `WEAVIATE_URL` | `http://<project>-weaviate:8080` | Weaviate URL |
| `EMBEDDING_MODEL` | `nomic-embed-text:v1.5` | Model for generating embeddings |

## Security

| Variable | Default | Description |
|----------|---------|-------------|
| `GUARDIAN_URL` | `http://<project>-guardian:11438` | Guardian service URL |
| `OPA_URL` | `http://<project>-opa:8181` | OPA policy engine URL |
| `A2A_VALIDATION_MODE` | `permissive` | strict, permissive, or disabled |
| `A2A_ENABLE_AUDIT_LOG` | `true` | Log all A2A validation attempts |
| `MAX_RISK_THRESHOLD` | `0.7` | Block requests above this risk score |
| `VALIDATION_MODE` | `permissive` | Semantic Layer validation mode |
| `REQUIRE_USER_VALIDATION` | `false` | Require user email for MCP calls |

## Artifact Store (MinIO)

| Variable | Default | Description |
|----------|---------|-------------|
| `ARTIFACT_ENDPOINT` | `http://<project>-minio:9000` | MinIO URL |
| `ARTIFACT_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `ARTIFACT_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `ARTIFACT_BUCKET` | `abi-artifacts` | Default bucket |
| `LOG_TO_ARTIFACT_STORE` | `true` | Upload execution logs to MinIO |
| `LOG_AGENT_NAME` | agent name | Identifier in log bucket |
| `LOG_BUCKET` | `abi-logs` | Bucket for logs |

## Ollama control

| Variable | Default | Description |
|----------|---------|-------------|
| `START_OLLAMA` | `false` | Start local Ollama in container (distributed mode) |
| `LOAD_MODELS` | `false` | Pull models on container start |

## Agent card

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_CARD` | `./agent_cards/<name>_agent.json` | Path to agent card file |
