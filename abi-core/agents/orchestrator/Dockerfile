FROM abi-llm-base

# Copy orchestrator-specific files without overwriting base agent files
COPY ./agent/*.py /app/agent/
COPY ./agent/models/*.py /app/agent/models/

RUN chmod +x /opt/abi/agents.d/start.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
