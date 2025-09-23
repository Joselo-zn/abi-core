FROM abi-llm-base

# Install additional dependencies for OPA integration
RUN pip install httpx

COPY ./agent /app

WORKDIR /app

# Use the OPA-enabled main file
CMD ["python", "main_opa.py"]