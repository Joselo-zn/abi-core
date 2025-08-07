FROM alpine:latest

# Descargar el binario oficial
RUN apk add --no-cache curl unzip && \
    curl -L https://github.com/pocketbase/pocketbase/releases/download/v0.21.2/pocketbase_0.21.2_linux_amd64.zip -o pb.zip && \
    unzip pb.zip && \
    mv pocketbase /usr/local/bin/pocketbase && \
    chmod +x /usr/local/bin/pocketbase && \
    rm pb.zip

EXPOSE 8080
VOLUME /pb/pocketbase_data

CMD [ "pocketbase", "serve", "--http=0.0.0.0:8080", "--dir", "/pb/pocketbase_data" ]