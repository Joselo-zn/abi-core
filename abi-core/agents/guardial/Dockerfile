FROM abi-llm-base

# Install system dependencies for cryptography
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    python3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install additional dependencies for secure OPA integration
RUN pip install --no-cache-dir \
    httpx \
    pyyaml \
    cryptography \
    cffi

# Copy guardial-specific files without overwriting base agent files
COPY ./agent/*.py /app/agent/
COPY ./agent/models /app/agent/models

# Copy guardial-specific OPA policies (these will override/extend base policies)
COPY ./opa/policies /app/opa/policies

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]