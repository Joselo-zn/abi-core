FROM ollama/ollama:latest

# 1. Install system packages and Python 3 with pip
RUN apt-get update && apt-get install -y \
    curl unzip gnupg cron lsb-release python3 python3-pip build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python libraries used by all agents
RUN pip3 install --no-cache-dir --break-system-packages \
    langchain \
    fastapi \
    mcp \
    mcp-toolbox \
    python-a2a \
    redis \
    tinydb

# Copia el script de inicio
COPY ./start.sh /start.sh
RUN chmod +x /start.sh

# 3. Set default working directory (agents will override if needed)
WORKDIR /app

ENTRYPOINT ["/start.sh"]
