FROM ollama/ollama:latest

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# 1. Install system packages and Python 3.11 with pip
RUN apt-get update && apt-get install -y \
    curl unzip gnupg cron lsb-release build-essential software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y python3.11 python3.11-dev python3.11-venv python3.11-distutils \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip3 pip3 /usr/local/bin/pip3.11 1 \
    && rm -rf /var/lib/apt/lists/*


# 3. Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY agents.d/ /opt/abi/agents.d/
COPY shared/abi-motd /etc/abi-motd
COPY shared/abi-motd.sh  /etc/profile.d/abi-motd.sh
COPY agent /app/agent
COPY agent_cards /app/agent_cards
COPY common /app/common
COPY mcp /app/mcp

RUN chmod +x /etc/profile.d/abi-motd.sh
RUN chmod +x /opt/abi/agents.d/abi-base.sh
RUN chmod +x /opt/abi/agents.d/start.sh

# 4. Set default working directory (agents will override if needed)
WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/abi-base.sh"]
