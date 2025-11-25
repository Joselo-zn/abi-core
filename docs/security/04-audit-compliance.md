# Auditoría y Compliance

Guardian registra todas las acciones para auditoría y cumplimiento normativo.

## Logs de Auditoría

Guardian registra:
- Quién hizo qué
- Cuándo lo hizo
- Resultado de la acción
- Políticas evaluadas

## Ver Logs

```bash
docker-compose logs guardian
```

## Dashboard de Auditoría

Accede al dashboard:
```
http://localhost:8080/audit
```

Verás:
- Historial de acciones
- Políticas violadas
- Alertas de seguridad
- Métricas de compliance

## Exportar Logs

```bash
# Exportar logs a archivo
docker-compose logs guardian > audit.log
```

## Próximos Pasos

- [Model serving](../production/01-model-serving.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
