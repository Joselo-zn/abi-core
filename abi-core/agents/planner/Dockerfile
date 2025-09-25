FROM abi-llm-base

# Copy planner-specific files without overwriting base agent files
COPY ./agent/planner.py /app/agent/
COPY ./agent/main.py /app/agent/
COPY ./agent/models /app/agent/models

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
