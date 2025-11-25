# Troubleshooting

Soluciones a problemas comunes.

## Agente No Responde

**Síntoma**: Timeout al llamar agente

**Soluciones**:
```bash
# 1. Verificar que está corriendo
docker-compose ps

# 2. Ver logs
docker-compose logs mi-agente-agent

# 3. Reiniciar
docker-compose restart mi-agente-agent
```

## Puerto en Uso

**Síntoma**: "Port already in use"

**Solución**: Cambiar puerto en `compose.yaml`:
```yaml
ports:
  - "9000:8000"  # Usar 9000 en lugar de 8000
```

## Modelo No Encontrado

**Síntoma**: "Model not found"

**Solución**:
```bash
# Descargar modelo
docker exec mi-proyecto-ollama ollama pull qwen2.5:3b

# O reprovisionar
abi-core provision-models
```

## Agente Lento

**Causas**:
- Modelo muy grande
- Poco RAM
- CPU lento

**Soluciones**:
```bash
# Usar modelo más pequeño
docker exec mi-proyecto-ollama ollama pull phi3:mini

# Actualizar configuración
# Editar .abi/runtime.yaml:
# model: phi3:mini
```

## Semantic Layer No Encuentra Agentes

**Soluciones**:
```bash
# 1. Verificar agent cards existen
ls services/semantic_layer/layer/mcp_server/agent_cards/

# 2. Reiniciar semantic layer
docker-compose restart semantic-layer

# 3. Ver logs
docker-compose logs semantic-layer
```

## Próximos Pasos

- [Deployment](04-deployment.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
