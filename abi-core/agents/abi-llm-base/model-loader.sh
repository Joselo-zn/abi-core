#!/bin/sh

MODEL_NAME="mixtral:8x22b"
HOSTS="http://orchestrator:11434 http://auditor:11435 http://verifier:11437 http://observer:11439 http://actor:11438"

for OLLAMA_HOST in $HOSTS; do
  echo "🚦 Waiting for Ollama at $OLLAMA_HOST to be ready..."

  until curl -s "$OLLAMA_HOST/api/tags" > /dev/null; do
    sleep 2
  done

  echo "🔍 Verifying if the model '$MODEL_NAME' is already installed on $OLLAMA_HOST..."
  if curl -s "$OLLAMA_HOST/api/tags" | grep -q "$MODEL_NAME"; then
    echo "✅ Model '$MODEL_NAME' already installed on $OLLAMA_HOST."
  else
    echo "⬇️ Starting download of the model on $OLLAMA_HOST..."
    curl -X POST "$OLLAMA_HOST/api/pull" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$MODEL_NAME\"}"
  fi

  echo "⏳ Waiting for the download to finish on $OLLAMA_HOST..."
  until curl -s "$OLLAMA_HOST/api/tags" | grep -q "$MODEL_NAME"; do
    echo "⏱  Still downloading on $OLLAMA_HOST..."
    sleep 10
  done

  echo "✅ Model '$MODEL_NAME' is up and running on $OLLAMA_HOST."
done
