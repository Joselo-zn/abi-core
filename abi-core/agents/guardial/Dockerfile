FROM abi-llm-base

# Install additional dependencies for secure OPA integration
RUN pip install httpx pyyaml

COPY ./agent /app

WORKDIR /app

# Use the main file with security validation
CMD ["python", "main.py"]