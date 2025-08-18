#!/usr/bin/env bash
set -euo pipefail

export TERM="${TERM:-dumb}"
export FORCE_ABI_MOTD=1
[[ -f /etc/profile.d/abi-motd.sh ]] && source /etc/profile.d/abi-motd.sh || true

START_OLLAMA="${START_OLLAMA:-true}"

pids=()

if [ "$START_OLLAMA" = "true" ]; then
  echo "🧠 Starting Ollama..."
  ollama serve &
  pids+=($!)
  # espera a que /api/tags responda (máx 60s)
  for i in $(seq 1 60); do
    if curl -fsS http://0.0.0.0:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "🚀 Starting ABI AGENT API..."
python3 -m agent.main &
pids+=($!)

# manejo de señales para apagar ambos
term() { 
  echo "⚠️  Caught SIGTERM, stopping..."
  kill -TERM "${pids[@]}" 2>/dev/null || true
}
trap term TERM INT

# espera a que cualquiera termine y propaga
wait -n "${pids[@]}"
rc=$?
kill -TERM "${pids[@]}" 2>/dev/null || true
wait || true
exit $rc
