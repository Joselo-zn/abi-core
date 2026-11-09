# abi-sandbox-data — abi-sandbox-python + pandas and openpyxl, for the data
# analyses of Back Office (back-office-route.md, decision 7). Build from
# abi_core_framework/sandbox-images (after the python image):
#   docker build -f data/Dockerfile -t abi-sandbox-data:latest .
#
# Same isolation as the python image: no network, user 10001, the files come
# in the bundle and the result leaves in .result.json.
ARG BASE_IMAGE=abi-sandbox-python:latest
FROM ${BASE_IMAGE}

USER root
RUN pip install --no-cache-dir pandas==2.3.3 openpyxl==3.1.5
USER 10001:10001
