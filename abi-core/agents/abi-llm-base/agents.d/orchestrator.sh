#!/usr/bin/env bash
set -euo pipefail

# MOTD sin reventar por TERM/TTY
export TERM="${TERM:-dumb}"
export FORCE_ABI_MOTD=1
[[ -f /etc/profile.d/abi-motd.sh ]] && source /etc/profile.d/abi-motd.sh || true

echo "🧠 Starting Ollama..."
# Si ya defines OLLAMA_HOST en el entorno, no hace falta --host
exec ollama serve

python3 "-m agent.main"
