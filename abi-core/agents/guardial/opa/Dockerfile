FROM openpolicyagent/opa:latest-envoy

# Copy policies and configuration
COPY ./policies /policies
COPY ./opa.yaml /config.yaml

# Expose OPA port
EXPOSE 8181

# Start OPA with configuration
ENTRYPOINT ["opa", "run", "--server", "--config-file=/config.yaml", "/policies"]