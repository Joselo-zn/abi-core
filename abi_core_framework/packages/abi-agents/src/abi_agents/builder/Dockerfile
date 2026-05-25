# Builder Agent Dockerfile
# Part of ABI Swarm

FROM agentbase/abi-image-v2:latest

WORKDIR /app

COPY requirements.txt /tmp/builder-requirements.txt
RUN pip install --no-cache-dir -r /tmp/builder-requirements.txt && \
    rm /tmp/builder-requirements.txt

COPY . /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ABI_ROLE="Builder Agent"
ENV ABI_NODE="ABI AGENT"
ENV AGENT_HOST=0.0.0.0

ENV START_OLLAMA=false
ENV LOAD_MODELS=false
ENV SERVICE_MODULE=main

ENV AGENT_PORT=11439
ENV SERVICE_PORT=11439
ENV AGENT_CARD=./agent_cards/builder_agent.json
ENV MODEL_NAME=qwen2.5:3b

RUN useradd -m -u 1000 builder && \
    chown -R builder:builder /app && \
    chmod -R 755 /root/.ollama || true

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:11439/health >/dev/null 2>&1 || exit 1

EXPOSE 11439
EXPOSE 11434

VOLUME ["/root/.ollama"]
