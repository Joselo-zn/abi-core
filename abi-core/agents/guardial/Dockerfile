FROM abi-llm-base

# Install additional dependencies for secure OPA integration
RUN pip install httpx pyyaml

COPY ./agent /app

WORKDIR /app

# Use the secure main file with mandatory security validation
CMD ["python", "main_secure.py"]