#!/usr/bin/env bash
set -euo pipefail

# ABI Generic Entrypoint
# Adaptable for all ABI services (Agents, Semantic Layer, Guardian, MCP-API)

export TERM="${TERM:-dumb}"
export FORCE_ABI_MOTD=1
[[ -f /etc/profile.d/abi-motd.sh ]] && source /etc/profile.d/abi-motd.sh || true

# Configuration variables
START_OLLAMA="${START_OLLAMA:-false}"           # Default: no Ollama (services opt-in)
SERVICE_COMMAND="${SERVICE_COMMAND:-}"          # Main service command
SERVICE_MODULE="${SERVICE_MODULE:-}"            # Python module to run
SERVICE_PORT="${SERVICE_PORT:-8000}"            # Default service port

pids=()

_safe_tput() {
  command -v tput >/dev/null 2>&1 || return 0
  local term="${TERM:-dumb}"
  tput -T "$term" "$1" 2>/dev/null || true
}

BOLD="$(_safe_tput bold)"
RESET="$(_safe_tput sgr0)"
ROLE="${ABI_ROLE:-Generic Service}"

# Function to start Ollama if needed
start_ollama() {
  echo "🧠 Starting Ollama for ${BOLD}${ROLE}${RESET}..."
  ollama serve &
  pids+=($!)
  
  # Wait for Ollama to be ready (max 60s)
  for i in $(seq 1 60); do
    if curl -fsS http://0.0.0.0:11434/api/tags >/dev/null 2>&1; then
      echo "✅ Ollama ready"
      break
    fi
    sleep 1
  done
}



# Function to start the main service
start_service() {
  if [[ -n "${SERVICE_COMMAND}" ]]; then
    echo "🚀 Starting service: ${SERVICE_COMMAND}"
    ${SERVICE_COMMAND} &
    pids+=($!)
  elif [[ -n "${SERVICE_MODULE}" ]]; then
    echo "🚀 Starting Python module: ${SERVICE_MODULE}"
    python3 -m "${SERVICE_MODULE}" &
    pids+=($!)
  elif [[ -f "main.py" ]]; then
    echo "🚀 Starting main.py..."
    python3 main.py &
    pids+=($!)
  else
    echo "❌ No service command specified. Set SERVICE_COMMAND or SERVICE_MODULE"
    exit 1
  fi
}

# Signal handler for graceful shutdown
term() { 
  echo "⚠️  Caught SIGTERM, stopping services..."
  kill -TERM "${pids[@]}" 2>/dev/null || true
}
trap term TERM INT

# Main execution flow
echo "🔧 Initializing ${BOLD}${ROLE}${RESET}..."

# Start Ollama if requested
if [ "$START_OLLAMA" = "true" ]; then
  start_ollama
fi

# Start the main service
start_service

echo "✅ ${BOLD}${ROLE}${RESET} started successfully"
echo "🌐 Service available on port ${SERVICE_PORT}"

# Wait for any process to end and propagate exit code
wait -n "${pids[@]}"
rc=$?
kill -TERM "${pids[@]}" 2>/dev/null || true
wait || true
exit $rc