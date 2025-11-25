# Monitoreo y Logs

Monitorea tu sistema de agentes en producción.

## Ver Logs

### Todos los servicios
```bash
docker-compose logs -f
```

### Servicio específico
```bash
docker-compose logs -f mi-agente-agent
```

### Últimas N líneas
```bash
docker-compose logs --tail=100 mi-agente-agent
```

## Estado de Servicios

```bash
# Ver estado
docker-compose ps

# Ver recursos
docker stats
```

## Métricas

### Guardian Dashboard
```
http://localhost:8080
```

Muestra:
- Agentes activos
- Requests por segundo
- Errores
- Latencia

## Alertas

Configura alertas en `services/guardian/alerting_config.json`:

```json
{
  "alerts": [
    {
      "name": "high_error_rate",
      "condition": "error_rate > 0.1",
      "action": "send_email"
    }
  ]
}
```

## Próximos Pasos

- [Troubleshooting](03-troubleshooting.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
