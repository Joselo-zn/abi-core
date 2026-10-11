# abi-sandbox-python — base image for running generated code in isolation.
# Build from abi_core_framework/sandbox-images:
#   docker build -f python/Dockerfile -t abi-sandbox-python:latest .
#
# No network at run time: every library a deliverable may import has to be
# installed here. A missing package is reported as a finding, never
# installed during a run.
FROM python:3.12-slim

RUN pip install --no-cache-dir numpy \
    && groupadd --gid 10001 sandbox \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /workspace --shell /usr/sbin/nologin sandbox \
    && mkdir -p /workspace /opt/abi-sandbox

COPY entry.py /opt/abi-sandbox/entry.py

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/workspace

WORKDIR /workspace
USER 10001:10001
ENTRYPOINT ["python", "/opt/abi-sandbox/entry.py"]
