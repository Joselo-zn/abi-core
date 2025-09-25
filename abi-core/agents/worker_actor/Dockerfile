FROM abi-llm-base

# Create models directory if it doesn't exist
RUN mkdir -p /app/agent/models

# Copy worker_actor-specific files without overwriting base agent files
COPY ./agent/worker_actor.py /app/agent/
COPY ./agent/main.py /app/agent/
COPY ./agent/models/agent_models.py /app/agent/models/

RUN chmod +x /opt/abi/agents.d/start.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
