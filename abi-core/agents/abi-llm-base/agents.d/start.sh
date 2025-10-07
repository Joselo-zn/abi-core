#!/usr/bin/env bash
set -euo pipefail

export TERM="${TERM:-dumb}"
export FORCE_ABI_MOTD=1
[[ -f /etc/profile.d/abi-motd.sh ]] && source /etc/profile.d/abi-motd.sh || true

START_OLLAMA="${START_OLLAMA:-true}"

pids=()

if [ "$START_OLLAMA" = "true" ]; then

  BOLD="$(_safe_tput bold)"
  RESET="$(_safe_tput sgr0)"
  ROLE="${ABI_ROLE:-Generic}"

  echo "🧠 Starting Ollama ${BOLD}${ROLE}${RESET}..."
  ollama serve &
  pids+=($!)
  # Waits to /api/tags answer (máx 60s)
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

term() { 
  echo "⚠️  Caught SIGTERM, stopping..."
  kill -TERM "${pids[@]}" 2>/dev/null || true
}
trap term TERM INT

# Waits to cualquiera ends and propagates
wait -n "${pids[@]}"
rc=$?
kill -TERM "${pids[@]}" 2>/dev/null || true
wait || true
exit $rc
