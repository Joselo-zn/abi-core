# abi-sandbox-pygame — abi-sandbox-python + pygame, for game deliverables.
# Build from abi_core_framework/sandbox-images (after the python image):
#   docker build -f pygame/Dockerfile -t abi-sandbox-pygame:latest .
#
# Runs headless: the domain adapter sets SDL_VIDEODRIVER=dummy and
# SDL_AUDIODRIVER=dummy (pygame's manylinux wheel bundles SDL).
ARG BASE_IMAGE=abi-sandbox-python:latest
FROM ${BASE_IMAGE}

USER root
# libglib2.0-0: pygame.mixer needs libgthread-2.0.so.0, absent from
# python:slim. Without it any deliverable that creates a Sound failed in the
# sandbox ("mixer module not available") while it works on a normal machine
# — a false error that sent the integration repair after a non-bug
# (live 2026-10-06).
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pygame
USER 10001:10001
