# Installation

## Requirements

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployments)
- Ollama (for LLM model serving)

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

## Install Ollama

ABI-Core uses Ollama for LLM model serving. Install it from [ollama.ai](https://ollama.ai):

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

Start Ollama:

```bash
ollama serve
```

Pull the default model (recommended for agents):

```bash
ollama pull qwen2.5:3b
```

This model has excellent tool/function calling support, which is essential for agent workflows.

## Next Steps

- [Quick Start Guide](quickstart.md) - Create your first project
- [Core Concepts](concepts.md) - Understand ABI-Core architecture
