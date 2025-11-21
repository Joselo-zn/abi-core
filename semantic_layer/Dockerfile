FROM python:3.11-slim

#Avoid interacting prompt
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY layer/ /app/layer

ENV PYTHONPATH=/app

EXPOSE 10100

CMD ["python", "-m", "layer.mcp_server.main"]
