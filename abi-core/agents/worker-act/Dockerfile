FROM abi-llm-base

# Copia el script de inicio
COPY ./start.sh /start.sh
RUN chmod +x /start.sh

COPY ./agent /app

WORKDIR /app

ENTRYPOINT ["/start.sh"]
