#!/bin/sh
set -euo pipefail

# ==============================
# Powered by ABI
# Developed by Jose Luis Martinez
# ==============================
# Model test: llama3.2:3b

MODEL_NAME="${MODEL_NAME:-llama3.2:3b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text:v1.5}"

HOSTS="${HOSTS:-http://abi-orchestrator:11434 http://abi-auditor:11435 http://abi-verifier:11437 http://abi-observer:11439 http://abi-actor:11438}"

EMBED_HOST="${EMBED_HOST:-http://abi-llm-base:11434}"

READY_WAIT_SECS="${READY_WAIT_SECS:-2}"
PULL_POLL_SECS="${PULL_POLL_SECS:-10}"
TIMEOUT_SECS="${TIMEOUT_SECS:-900}"

ts() { date '+%H:%M:%S'; }

wait_ollama() {
  host="$1"
  echo "[$(ts)] 🚦 Waiting Ollama in $host ..."
  start=$(date +%s)
  until curl -fsS "$host/api/tags" >/dev/null 2>&1; do
    now=$(date +%s); [ $((now-start)) -ge "$TIMEOUT_SECS" ] && {
      echo "[$(ts)] ❌ Timeout waiting Ollama in $host"; exit 1; }
    sleep "$READY_WAIT_SECS"
  done
  echo "[$(ts)] ✅ Ollama ready in $host"
}

has_model() {
  host="$1"; model="$2"
  curl -fsS "$host/api/tags" | grep -q "\"$model\""
}

pull_model() {
  host="$1"; model="$2"
  echo "[$(ts)] ⬇️ Downloading '$model' in $host ..."

  curl -fsS -X POST "$host/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$model\"}" >/dev/null || true

  start=$(date +%s)
  until has_model "$host" "$model"; do
    now=$(date +%s); [ $((now-start)) -ge "$TIMEOUT_SECS" ] && {
      echo "[$(ts)] ❌ Timeout downloading '$model' in $host"; exit 2; }
    echo "[$(ts)] ⏱  downloading '$model' in $host ..."
    sleep "$PULL_POLL_SECS"
  done
  echo "[$(ts)] ✅ Model '$model' available in $host"
}

ensure_model() {
  host="$1"; model="$2"
  wait_ollama "$host"
  if has_model "$host" "$model"; then
    echo "[$(ts)] ✅ '$model' already installed in $host"
  else
    pull_model "$host" "$model"
  fi
}

for OLLAMA_HOST in $HOSTS; do
  echo "-----------------------------------------------"
  echo "[$(ts)] 🔧 Getting ready LLM '$MODEL_NAME' in $OLLAMA_HOST"
  ensure_model "$OLLAMA_HOST" "$MODEL_NAME"
done

echo "=============================="
echo "🚀 Powered By ABI"
echo "=============================="

echo "-----------------------------------------------"
echo "[$(ts)] 🔧 Getting ready EMBEDDINGS '$EMBEDDING_MODEL' en $EMBED_HOST"
ensure_model "$EMBED_HOST" "$EMBEDDING_MODEL"

echo "-----------------------------------------------"
echo "[$(ts)] 🎉 All set: LLM='$MODEL_NAME' in HOSTS & EMBEDDINGS='$EMBEDDING_MODEL' in $EMBED_HOST"
