# Deployment

Despliega tu sistema de agentes en producción.

## Docker Compose (Simple)

```bash
# Iniciar en producción
docker-compose up -d

# Escalar agentes
docker-compose up -d --scale mi-agente=3
```

## Docker Swarm (Cluster)

```bash
# Inicializar swarm
docker swarm init

# Desplegar stack
docker stack deploy -c compose.yaml mi-sistema

# Ver servicios
docker service ls

# Escalar
docker service scale mi-sistema_mi-agente=5
```

## Kubernetes (Avanzado)

```bash
# Generar manifiestos
kompose convert -f compose.yaml

# Aplicar
kubectl apply -f .

# Ver pods
kubectl get pods

# Escalar
kubectl scale deployment mi-agente --replicas=3
```

## Variables de Entorno

Configura en producción:

```bash
# .env
MODEL_NAME=qwen2.5:3b
OLLAMA_HOST=http://ollama:11434
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## Seguridad en Producción

1. **Usar HTTPS**
2. **Configurar firewalls**
3. **Rotar secrets**
4. **Habilitar autenticación**
5. **Monitorear logs**

## Backup

```bash
# Backup de volúmenes
docker run --rm -v mi-proyecto_ollama_data:/data \
  -v $(pwd):/backup alpine \
  tar czf /backup/ollama-backup.tar.gz /data

# Backup de configuración
tar czf config-backup.tar.gz .abi/ services/
```

## Próximos Pasos

- [Referencia CLI](../reference/cli-reference.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
