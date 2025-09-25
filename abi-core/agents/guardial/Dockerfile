FROM abi-llm-base

# Install additional dependencies for secure OPA integration
RUN pip install httpx pyyaml

# Copy guardial-specific files without overwriting base agent files
COPY ./agent/*.py /app/agent/
COPY ./agent/models /app/agent/models

WORKDIR /app

# Use the main file with security validation
CMD ["python", "agent/main.py"]