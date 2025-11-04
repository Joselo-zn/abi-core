# 👁️ ABI Observer Agent

El Observer Agent es el sistema de monitoreo y observabilidad del ecosistema ABI. Proporciona análisis en tiempo real, detección de anomalías y reportes comprensivos del estado del sistema.

## 🚀 Inicio Rápido

### 1. Levantar el sistema completo
```bash
cd abi-core
docker-compose up -d
```

### 2. Verificar que el Observer está funcionando
```bash
# Verificar logs
docker-compose logs abi-observer

# Probar API
./test_observer_api.sh
```

## 🌐 Acceso a Reportes

### Dashboard Web
- **URL**: http://localhost:8090
- **Descripción**: Interfaz web interactiva con gráficos y métricas en tiempo real
- **Características**:
  - Health Score visual
  - Gráficos de rendimiento
  - Lista de anomalías
  - Stream de eventos
  - Auto-refresh cada 30s

### API REST
Base URL: `http://localhost:8090/api/`

| Endpoint | Descripción | Ejemplo |
|----------|-------------|---------|
| `/health` | Análisis de salud del sistema | `curl http://localhost:8090/api/health` |
| `/anomalies` | Anomalías detectadas | `curl http://localhost:8090/api/anomalies` |
| `/performance` | Métricas de rendimiento por agente | `curl http://localhost:8090/api/performance` |
| `/events?hours=N` | Eventos recientes | `curl http://localhost:8090/api/events?hours=2` |
| `/report` | Reporte comprensivo | `curl http://localhost:8090/api/report` |
| `/metrics/system` | Métricas del sistema | `curl http://localhost:8090/api/metrics/system` |

### CLI Reporter
```bash
# Instalar CLI (dentro del contenedor)
docker exec -it abi-core-abi-observer-1 bash
cd /app && ./install_cli.sh

# Comandos disponibles
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py health
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py anomalies
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py performance
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py events --hours 2
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py report
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py monitor --interval 10
```

## 📊 Funcionalidades

### 1. System Health Monitoring
- Métricas en tiempo real del sistema
- Health Score (0-100%)
- Análisis con LLM para insights inteligentes

### 2. Anomaly Detection
- Detección de fallos repetidos
- Agentes inactivos
- Degradación de rendimiento
- Patrones anómalos

### 3. Event Stream Analysis
- Registro de eventos entre agentes
- Análisis de patrones de interacción
- Historial configurable

### 4. Performance Analysis
- Métricas por agente individual
- Success rates y tiempos de respuesta
- Comparación y benchmarking

### 5. Observation Reporting
- Reportes comprensivos con recomendaciones
- Análisis inteligente con LLM
- Exportación en múltiples formatos

## 🔧 Configuración

### Variables de Entorno
```bash
AGENT_HOST=0.0.0.0
AGENT_BASE=https://abi-observer:8004
AGENT_CARD=/app/agent_cards/observer_agent.json
ABI_ROLE=Observer Agent
ABI_NODE=ABI AGENT
PYTHONPATH=/app
```

### Puertos
- **8004**: Protocolo A2A (comunicación entre agentes)
- **8080**: API REST y Dashboard (mapeado a 8090 en host)

## 🧪 Testing

### Probar API completa
```bash
./test_observer_api.sh
```

### Probar endpoints individuales
```bash
# Health check
curl http://localhost:8090/api/health | jq

# Ver anomalías
curl http://localhost:8090/api/anomalies | jq

# Métricas de rendimiento
curl http://localhost:8090/api/performance | jq
```

### Monitoreo en vivo
```bash
# Via CLI
docker exec -it abi-core-abi-observer-1 python /app/agent/cli_reporter.py monitor

# Via web
open http://localhost:8090
```

## 🐛 Troubleshooting

### Observer no responde
```bash
# Verificar logs
docker-compose logs abi-observer

# Reiniciar servicio
docker-compose restart abi-observer
```

### API no accesible
```bash
# Verificar puertos
docker-compose ps abi-observer

# Verificar conectividad
curl -v http://localhost:8090/api/health
```

### Sin datos en reportes
```bash
# Verificar que otros agentes estén funcionando
docker-compose ps

# Generar actividad de prueba
curl -X POST http://localhost:11435/some-test-endpoint
```

## 📈 Métricas Clave

### Health Score
- **90-100%**: Sistema óptimo
- **70-89%**: Funcionamiento normal con alertas menores
- **50-69%**: Problemas detectados, requiere atención
- **<50%**: Estado crítico, intervención inmediata

### Anomalías por Severidad
- **High**: Fallos críticos, múltiples errores
- **Medium**: Degradación de rendimiento, agentes inactivos
- **Low**: Alertas informativas, patrones inusuales

## 🔗 Integración

### Con otros sistemas
```python
import requests

# Obtener health score
health = requests.get("http://localhost:8090/api/health").json()
score = health['health_score']

# Configurar alertas
if score < 0.7:
    send_alert(f"System health degraded: {score*100:.1f}%")
```

### Webhooks (futuro)
El Observer puede configurarse para enviar webhooks cuando se detecten anomalías críticas.

---

## 🎯 Casos de Uso

1. **Monitoreo 24/7**: Dashboard siempre visible para ops
2. **Alertas tempranas**: Detectar problemas antes de que escalen
3. **Debugging**: Analizar fallos y patrones problemáticos
4. **Optimización**: Identificar cuellos de botella
5. **Reporting**: Generar reportes para stakeholders
6. **Capacity Planning**: Analizar carga y planificar recursos

¡El Observer es tu ventana completa al estado del sistema ABI! 👁️✨