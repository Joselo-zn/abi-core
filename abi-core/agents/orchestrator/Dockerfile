FROM abi-llm-base

# Copy orchestrator-specific files without overwriting base agent files
COPY ./agent/orchestrator.py /app/agent/
COPY ./agent/main.py /app/agent/

RUN chmod +x /opt/abi/agents.d/start.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
