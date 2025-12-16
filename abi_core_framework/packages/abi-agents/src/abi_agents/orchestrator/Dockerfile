# Orchestrator Agent Dockerfile
# Part of ABI-Core Agentic Orchestration Layer

FROM smarbuy/abi-image:latest

# Set working directory
WORKDIR /app

# Copy agent-specific requirements and install
COPY requirements.txt /tmp/orchestrator-requirements.txt
RUN pip install --no-cache-dir -r /tmp/orchestrator-requirements.txt && \
    rm /tmp/orchestrator-requirements.txt

# Copy agent files
COPY . /app

# Environment variables for abi-entrypoint.sh
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="Orchestrator Agent"
ENV ABI_NODE="ABI AGENT"
ENV AGENT_HOST=0.0.0.0

# ABI Entrypoint configuration
# Default to centralized mode (START_OLLAMA=false)
# Override via docker-compose for distributed mode
ENV START_OLLAMA=false
ENV LOAD_MODELS=false
ENV SERVICE_MODULE=main

# Default values (will be overridden by docker-compose)
ENV AGENT_PORT=8002
ENV SERVICE_PORT=8002
ENV AGENT_CARD=./agent_cards/orchestrator_agent.json
ENV WEB_INTERFACE_PORT=8083
ENV MODEL_NAME=qwen2.5:3b

# Create non-root user but keep root for model access
RUN useradd -m -u 1000 orchestrator && \
    chown -R orchestrator:orchestrator /app && \
    chmod -R 755 /root/.ollama || true

# Health check - verify agent is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8002/health >/dev/null 2>&1 || exit 1

# Expose ports (agent + web interface + Ollama for distributed mode)
EXPOSE 8002
EXPOSE 8083
EXPOSE 11434

# Volume for model data (used in distributed mode)
VOLUME ["/root/.ollama"]

# Use abi-entrypoint.sh (inherited from abi-image)
# The entrypoint will handle Ollama startup, model loading, and agent startup
# No need to override CMD - entrypoint will use SERVICE_MODULE
