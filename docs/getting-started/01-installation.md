# Installation

Welcome to ABI-Core. This guide will help you install everything needed to start building AI agent systems.

## Requirements

Before starting, make sure you have:

- **Python 3.11 or higher**
- **Docker and Docker Compose** (for running agents and services)
- **4GB RAM minimum** (8GB recommended)
- **10GB disk space** (for AI models)

## Step 1: Install Python

### On Linux/macOS

Python 3.11+ is usually pre-installed. Check your version:

```bash
python3 --version
```

If you need to install it:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3-pip

# macOS (with Homebrew)
brew install python@3.11
```

### On Windows

Download Python from [python.org](https://www.python.org/downloads/) and follow the installer.

**Important**: Check "Add Python to PATH" during installation.

## Step 2: Install Docker

Docker is essential for running agents and services in containers.

### On Linux

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Restart session to apply changes
```

### On macOS/Windows

Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Verify Installation

```bash
docker --version
docker-compose --version
```

You should see something like:
```
Docker version 24.0.0
Docker Compose version v2.20.0
```

## Step 3: Install ABI-Core

### Install from PyPI (Recommended)

The easiest way is to install from PyPI:

```bash
pip install abi-core-ai
```

### Install from Source

For development or to get the latest features:

```bash
# Clone the repository
git clone https://github.com/Joselo-zn/abi-core.git
cd abi-core

# Install in development mode
pip install -e .
```

## Step 4: Verify Installation

Verify that ABI-Core installed correctly:

```bash
abi-core --version
```

You should see:
```
abi-core version 1.0.0
```

Check available commands:

```bash
abi-core --help
```

You should see:
```
Usage: abi-core [OPTIONS] COMMAND [ARGS]...

  ABI-Core CLI - Build AI agent systems

Commands:
  create            Create new projects and components
  add               Add components to existing project
  remove            Remove components from project
  provision-models  Download and configure LLM models
  run               Start the project services
  status            Check project and services status
  info              Show project information
```

## Troubleshooting

### Error: "command not found: abi-core"

**Cause**: Python is not in your PATH or pip installed in a non-included directory.

**Solution**:

```bash
# Find where it was installed
pip show abi-core-ai

# Add the bin directory to your PATH
export PATH="$HOME/.local/bin:$PATH"

# To make it permanent, add it to ~/.bashrc or ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Error: "Permission denied" when running Docker

**Cause**: Your user doesn't have permissions to run Docker.

**Solution**:

```bash
# Linux: Add user to docker group
sudo usermod -aG docker $USER

# Restart session
logout
# Log back in
```

### Error: "Python version too old"

**Cause**: You have Python 3.10 or earlier.

**Solution**: Install Python 3.11 or higher following Step 1 instructions.

## Next Steps

Congratulations! You have ABI-Core installed. Now you can:

1. [Understand what ABI-Core is](02-what-is-abi.md)
2. [Learn basic concepts](03-basic-concepts.md)
3. [Create your first project](04-first-project.md)

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Python Documentation](https://docs.python.org/3/)
- [ABI-Core Repository](https://github.com/Joselo-zn/abi-core)

---

**Need help?** Open an issue on [GitHub](https://github.com/Joselo-zn/abi-core/issues) or email jl.mrtz@gmail.com
