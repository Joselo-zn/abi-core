#!/bin/bash

# Inicia el servidor de Ollama en segundo plano
echo "🧠 Iniciando Ollama..."
ollama serve &
OLLAMA_PID=$!

# Espera unos segundos para que arranque Ollama
sleep 5

# Inicia la API del agente con Uvicorn
echo "🚀 Iniciando la API del agente..."
uvicorn main:app --host 0.0.0.0 --port 8001 &
UVICORN_PID=$!

# Espera a que ambos procesos terminen (si alguno se cae, el contenedor también)
wait $OLLAMA_PID
wait $UVICORN_PID
