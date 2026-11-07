# abi-sandbox-browser — abi-sandbox-python + headless Chromium, for HTML/JS
# deliverables. Build from abi_core_framework/sandbox-images (after the python image):
#   docker build -f browser/Dockerfile -t abi-sandbox-browser:latest .
#
# No network at run time: the browser comes with the image, and whatever the
# page asks from outside is recorded and refused by browser_check.py.
ARG BASE_IMAGE=abi-sandbox-python:latest
FROM ${BASE_IMAGE}

USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/abi-sandbox/browsers
RUN pip install --no-cache-dir playwright==1.56.0 \
    && playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*
COPY browser/browser_check.py /opt/abi-sandbox/browser_check.py
USER 10001:10001
