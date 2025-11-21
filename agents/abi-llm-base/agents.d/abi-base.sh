#!/usr/bin/env bash
set -euo pipefail

export TERM="${TERM:-dumb}"
export FORCE_ABI_MOTD=1
[[ -f /etc/profile.d/abi-motd.sh ]] && source /etc/profile.d/abi-motd.sh || true

echo "🧠 Starting Ollama from base..."

exec ollama serve
