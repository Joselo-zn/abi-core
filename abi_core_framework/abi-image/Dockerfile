# ABI Base Image v2
# Optimized: no bundled Ollama, smaller footprint
# Ollama runs as a separate service in compose
# Updated: 2026-05-13

FROM python:3.12-slim AS builder

# Build dependencies (only needed for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- Final stage ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy ABI scripts and banner
COPY agents.d/ /opt/abi/agents.d/
COPY shared/abi-motd /etc/abi-motd
COPY shared/abi-motd.sh /etc/profile.d/abi-motd.sh
COPY agent_cards /app/agent_cards

RUN chmod +x /opt/abi/agents.d/*.sh && \
    chmod +x /etc/profile.d/abi-motd.sh

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose common agent port
EXPOSE 8000

# Health check (agent HTTP)
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set default entrypoint (can be overridden by services)
ENTRYPOINT ["/opt/abi/agents.d/abi-entrypoint.sh"]

CMD ["python", "-c", "print('ABI Image v2 Ready')"]
