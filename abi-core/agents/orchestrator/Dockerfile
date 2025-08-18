FROM abi-llm-base

COPY ./agent/main.py /app/agent
COPY ./agent/orchestrator.py /app/agent

RUN chmod +x /opt/abi/agents.d/start.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
