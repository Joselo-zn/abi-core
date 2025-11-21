FROM openpolicyagent/opa:latest

# Copy OPA server configuration for bundle management
COPY ./server-config.yaml /server-config.yaml

# Copy existing policies as fallback
COPY ./policies /policies

# Expose OPA port
EXPOSE 8181

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8181/health || exit 1

# Start OPA server with bundle management enabled
CMD ["run", "--server", "--addr=0.0.0.0:8181", "--config-file=/server-config.yaml", "/policies"]