FROM abi-llm-base

# Install additional dependencies for Observer
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Create directories
RUN mkdir -p /app/agent/models

# Copy observer-specific files
COPY ./agent/__init__.py /app/agent/
COPY ./agent/observer.py /app/agent/
COPY ./agent/cli_reporter.py /app/agent/
COPY ./agent/main.py /app/agent/

# Make CLI executable
RUN chmod +x /app/agent/cli_reporter.py

# Expose ports
EXPOSE 8004 8080

RUN chmod +x /opt/abi/agents.d/abi-entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/opt/abi/agents.d/abi-entrypoint.sh"]