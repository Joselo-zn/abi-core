FROM ollama/ollama:latest

# 1. Install system packages and Python 3 with pip
RUN apt-get update && apt-get install -y \
    curl unzip gnupg cron lsb-release python3 python3-pip build-essential \
    && rm -rf /var/lib/apt/lists/*

#@TODO Change it by requirements.txt
# 2. Install Python libraries used by all agents
RUN pip3 install --no-cache-dir --break-system-packages \
    langchain \
    fastapi \
    mcp \
    mcp-toolbox \
    a2a-sdk \
    uvicorn \
    redis \
    tinydb \
    httpx \
    networkx \
    langchain-community \
    starlette

COPY agents.d/ /opt/abi/agents.d/
COPY shared/abi-motd /etc/abi-motd
COPY shared/abi-motd.sh  /etc/profile.d/abi-motd.sh
COPY agent /app/agent
COPY agent_cards /app/agent_cards
COPY common /app/common
COPY mcp /app/mcp

RUN chmod +x /etc/profile.d/abi-motd.sh
RUN chmod +x /opt/abi/agents.d/abi-base.sh

# 3. Set default working directory (agents will override if needed)
WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/abi-base.sh"]
