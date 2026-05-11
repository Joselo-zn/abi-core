# Installation

You need 3 things: Python, Docker, and ABI-Core. That's it.

## What you need

| Tool | Why | How to get it |
|------|-----|---------------|
| Python 3.11+ | ABI-Core is written in Python | [python.org/downloads](https://www.python.org/downloads/) |
| Docker | Agents run inside containers | [docker.com/get-started](https://www.docker.com/products/docker-desktop/) |
| ABI-Core | The framework itself | `pip install abi-core-ai` |

## 1. Install Python

Open a terminal and check if you already have it:

```bash
python3 --version
```

If it says `Python 3.11` or higher, you're good. Skip to step 2.

If not, download it from [python.org](https://www.python.org/downloads/) and install it. On Windows, make sure to check **"Add Python to PATH"** during installation.

## 2. Install Docker

Download [Docker Desktop](https://www.docker.com/products/docker-desktop/) and install it. Works on Windows, Mac, and Linux.

Once installed, check it works:

```bash
docker --version
```

If you see a version number, you're good.

## 3. Install ABI-Core

```bash
pip install abi-core-ai
```

Done. Check it worked:

```bash
abi-core --help
```

You should see a list of commands like `create`, `add`, `run`.

## Something not working?

**"command not found: abi-core"** — Python installed it somewhere your terminal can't find. Run this:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then try `abi-core --help` again. If it works, make it permanent:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**"Permission denied" with Docker** — On Linux, add yourself to the docker group:

```bash
sudo usermod -aG docker $USER
```

Then log out and back in.

**Python version too old** — You need 3.11 or newer. Download the latest from [python.org](https://www.python.org/downloads/).

## Next step

👉 [What is ABI-Core?](02-what-is-abi.md)
