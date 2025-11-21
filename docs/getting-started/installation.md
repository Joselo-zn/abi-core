# Installation

## Requirements

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployments)

## Install from PyPI

The easiest way to install ABI-Core is via pip:

```bash
pip install abi-core-ai
```

## Install from Source

For development or to get the latest features:

```bash
# Clone the repository
git clone https://github.com/Joselo-zn/abi-core.git
cd abi-core

# Install in development mode
pip install -e .
```

## Verify Installation

Check that the CLI is installed correctly:

```bash
abi-core --version
abi-core --help
```

## Install Docker

ABI-Core uses Docker for running agents and services. Install Docker Desktop:

- **macOS/Windows**: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux**: Follow [official Docker installation guide](https://docs.docker.com/engine/install/)

Verify Docker installation:

```bash
docker --version
docker-compose --version
```

**Note:** Ollama and LLM models are automatically managed by ABI-Core through Docker. You don't need to install Ollama separately.

## Next Steps

- [Quick Start Guide](quickstart.md) - Create your first project
- [Core Concepts](concepts.md) - Understand ABI-Core architecture
