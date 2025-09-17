FROM abi-llm-base

COPY ./agent/*.py /app/agent
COPY ./agent/models /app/agent/models

RUN chmod +x /opt/abi/agents.d/start.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/start.sh"]
