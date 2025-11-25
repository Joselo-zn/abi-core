# Deployment

Deploy your agent system to production.

## Docker Compose (Simple)

```bash
# Start in production
docker-compose up -d

# Scale agents
docker-compose up -d --scale my-agent=3
```

## Docker Swarm (Cluster)

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c compose.yaml my-system

# View services
docker service ls

# Scale
docker service scale my-system_my-agent=5
```

## Kubernetes (Advanced)

```bash
# Generate manifests
kompose convert -f compose.yaml

# Apply
kubectl apply -f .

# View pods
kubectl get pods

# Scale
kubectl scale deployment my-agent --replicas=3
```

## Environment Variables

Configure in production:

```bash
# .env
MODEL_NAME=qwen2.5:3b
OLLAMA_HOST=http://ollama:11434
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## Production Security

1. **Use HTTPS**
2. **Configure firewalls**
3. **Rotate secrets**
4. **Enable authentication**
5. **Monitor logs**

## Backup

```bash
# Backup volumes
docker run --rm -v my-project_ollama_data:/data \
  -v $(pwd):/backup alpine \
  tar czf /backup/ollama-backup.tar.gz /data

# Backup configuration
tar czf config-backup.tar.gz .abi/ services/
```

## Next Steps

- [CLI Reference](../reference/cli-reference.md)

---

**Created by [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
