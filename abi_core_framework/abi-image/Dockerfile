# ABI Base Image - Single Stage
# Common dependencies for all ABI services

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
#RUN curl -fsSL https://ollama.ai/install.sh | sh

# Set working directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ABI scripts and banner
COPY agents.d/ /opt/abi/agents.d/
COPY shared/abi-motd /etc/abi-motd
COPY shared/abi-motd.sh /etc/profile.d/abi-motd.sh
COPY agent_cards /app/agent_cards

# Make scripts executable
RUN chmod +x /opt/abi/agents.d/*.sh
RUN chmod +x /etc/profile.d/abi-motd.sh

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tar \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# copy pre-downloaded ollama tarball (build context must contain ollama-linux-amd64.tgz)
COPY /abi-ollama/ollama-linux-amd64.tgz /tmp/ollama.tgz
COPY abi-ollama/install-ollama.sh /usr/local/bin/install-ollama.sh
RUN chmod +x /usr/local/bin/install-ollama.sh && \
    OLLAMA_TARBALL=/tmp/ollama.tgz /usr/local/bin/install-ollama.sh

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_MODELS=/root/.ollama/models

# Expose common ports
EXPOSE 8000 11434

# Health check
HEALTHCHECK --interval=45s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:11434/api/tags || exit 1

# Volume for model storage (shared with services)
VOLUME ["/root/.ollama"]

# Set default entrypoint (can be overridden by services)
ENTRYPOINT ["/opt/abi/agents.d/abi-entrypoint.sh"]

# Default command (can be overridden by services)
CMD ["python", "-c", "print('ABI Base Image Ready')"]