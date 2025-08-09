FROM python:3.11-slim

# Evita prompts de interacción
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia archivos de requirements
COPY requirements.txt .

# Instala dependencias de Python
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ /app/mcp_server/

ENV PYTHONPATH=/app

# Expone el puerto si aplica (ajústalo si usas FastAPI u otro framework con puerto específico)
EXPOSE 10100

# Comando para lanzar el servidor MCP
CMD ["python", "-m", "mcp_server.main"]

