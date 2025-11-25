# Conceptos Básicos

Antes de comenzar a construir, es importante entender algunos conceptos clave de ABI-Core.

## Agente (Agent)

Un **agente** es un programa de IA que puede:

- Entender y generar lenguaje natural
- Ejecutar tareas específicas
- Usar herramientas y funciones
- Comunicarse con otros agentes

**Analogía**: Piensa en un agente como un empleado especializado en tu empresa.

**Ejemplo**:
```python
# Un agente simple
class AsistenteAgente:
    def responder(self, pregunta):
        # Usa IA para responder
        return "Aquí está tu respuesta..."
```

## Proyecto (Project)

Un **proyecto** es un contenedor para tu sistema de agentes. Incluye:

- Uno o más agentes
- Servicios (capa semántica, seguridad)
- Configuración
- Archivos Docker

**Analogía**: Un proyecto es como una empresa con varios departamentos (agentes).

**Estructura**:
```
mi-proyecto/
├── agents/          # Tus agentes
├── services/        # Servicios de soporte
├── compose.yaml     # Configuración Docker
└── .abi/           # Metadatos del proyecto
```

## Agent Card (Tarjeta de Agente)

Una **agent card** es un documento que describe:

- Qué puede hacer el agente
- Cómo comunicarse con él
- Qué tareas soporta

**Analogía**: Es como una tarjeta de presentación profesional.

**Ejemplo**:
```json
{
  "name": "Agente Analista",
  "description": "Analiza datos de ventas",
  "url": "http://localhost:8000",
  "tasks": ["analizar_ventas", "generar_reporte"]
}
```

## Capa Semántica (Semantic Layer)

La **capa semántica** es un servicio que:

- Registra todos los agentes disponibles
- Encuentra el agente correcto para cada tarea
- Usa búsqueda inteligente (embeddings)

**Analogía**: Es como un directorio telefónico inteligente.

**Uso**:
```python
# Buscar un agente
agente = encontrar_agente("analizar datos de ventas")
# Retorna: Agente Analista
```

## A2A Protocol (Agent-to-Agent)

**A2A** es el protocolo que permite a los agentes comunicarse entre sí.

**Analogía**: Es como el email entre empleados de una empresa.

**Ejemplo**:
```python
# Agente A envía mensaje a Agente B
await agente_a.enviar_mensaje(
    destino="agente_b",
    mensaje="Analiza estos datos"
)
```

## LLM (Large Language Model)

Un **LLM** es el "cerebro" del agente. Es el modelo de IA que:

- Entiende lenguaje natural
- Genera respuestas
- Razona sobre problemas

**Modelos comunes**:
- `qwen2.5:3b` (por defecto en ABI-Core)
- `llama3.2:3b`
- `mistral:7b`

## Ollama

**Ollama** es el servidor que ejecuta los LLMs localmente.

**Analogía**: Es como tener tu propio servidor de IA en lugar de usar servicios en la nube.

**Ventajas**:
- ✅ Privacidad (todo local)
- ✅ Sin costos de API
- ✅ Sin límites de uso

## Model Serving (Servicio de Modelos)

Hay dos formas de servir modelos:

### Centralizado (Recomendado)

Un solo Ollama sirve a todos los agentes:

```
┌─────────────┐
│   Ollama    │ ← Todos los agentes usan este
└─────────────┘
      ↑
      ├─── Agente 1
      ├─── Agente 2
      └─── Agente 3
```

**Ventajas**: Menos recursos, más fácil de gestionar

### Distribuido

Cada agente tiene su propio Ollama:

```
Agente 1 ← Ollama 1
Agente 2 ← Ollama 2
Agente 3 ← Ollama 3
```

**Ventajas**: Aislamiento completo, versiones independientes

## Guardian

**Guardian** es el servicio de seguridad que:

- Controla permisos
- Registra todas las acciones
- Aplica políticas

**Analogía**: Es como el departamento de seguridad de una empresa.

## OPA (Open Policy Agent)

**OPA** es el motor que evalúa políticas de seguridad.

**Ejemplo de política**:
```rego
# Solo el agente de finanzas puede ejecutar transacciones
allow if {
    input.agent == "finanzas"
    input.action == "ejecutar_transaccion"
}
```

## Embeddings

Los **embeddings** son representaciones numéricas de texto que permiten:

- Buscar por significado (no solo palabras exactas)
- Encontrar contenido similar
- Agrupar información relacionada

**Ejemplo**:
```
"analizar ventas" → [0.2, 0.8, 0.1, ...]
"examinar ingresos" → [0.3, 0.7, 0.2, ...]
# Estos son similares!
```

## Weaviate

**Weaviate** es la base de datos vectorial que:

- Almacena embeddings
- Realiza búsquedas semánticas
- Encuentra agentes por capacidad

## Docker y Docker Compose

**Docker** empaqueta aplicaciones en contenedores.  
**Docker Compose** orquesta múltiples contenedores.

**Analogía**: Docker es como una caja de envío estándar, Docker Compose es el sistema de logística.

**En ABI-Core**:
```yaml
# compose.yaml
services:
  mi-agente:
    build: ./agents/mi-agente
    ports:
      - "8000:8000"
```

## Streaming

**Streaming** es enviar respuestas en tiempo real, palabra por palabra.

**Sin streaming**:
```
Usuario: "Explica la IA"
[espera 10 segundos]
Agente: "La inteligencia artificial es..."
```

**Con streaming**:
```
Usuario: "Explica la IA"
Agente: "La" "inteligencia" "artificial" "es"...
```

## Context ID y Task ID

- **Context ID**: Identifica una conversación completa
- **Task ID**: Identifica una tarea específica

**Ejemplo**:
```
Context ID: "conversacion-001"
  ├─ Task ID: "pregunta-1"
  ├─ Task ID: "pregunta-2"
  └─ Task ID: "pregunta-3"
```

## Workflow (Flujo de Trabajo)

Un **workflow** es una secuencia de tareas ejecutadas por múltiples agentes.

**Ejemplo**:
```
1. Agente Recolector → Obtiene datos
2. Agente Analista → Analiza datos
3. Agente Reportero → Genera reporte
```

## Planner y Orchestrator

- **Planner**: Divide tareas complejas en subtareas
- **Orchestrator**: Ejecuta las subtareas y coordina agentes

**Ejemplo**:
```
Usuario: "Analiza ventas y genera reporte"

Planner:
  ├─ Tarea 1: Analizar ventas → Agente Analista
  └─ Tarea 2: Generar reporte → Agente Reportero

Orchestrator:
  ├─ Ejecuta Tarea 1
  ├─ Ejecuta Tarea 2
  └─ Combina resultados
```

## MCP (Model Context Protocol)

**MCP** es el protocolo para comunicación entre agentes y la capa semántica.

**Funciones principales**:
- `find_agent()`: Buscar un agente
- `list_agents()`: Listar todos los agentes
- `check_health()`: Verificar estado de un agente

## Glosario Rápido

| Término | Significado |
|---------|-------------|
| **Agent** | Programa de IA que ejecuta tareas |
| **Agent Card** | Descripción de capacidades de un agente |
| **A2A** | Protocolo de comunicación entre agentes |
| **LLM** | Modelo de lenguaje (cerebro del agente) |
| **Ollama** | Servidor para ejecutar LLMs localmente |
| **Semantic Layer** | Servicio de descubrimiento de agentes |
| **Guardian** | Servicio de seguridad y políticas |
| **OPA** | Motor de evaluación de políticas |
| **Embeddings** | Representación numérica de texto |
| **Weaviate** | Base de datos vectorial |
| **Streaming** | Respuestas en tiempo real |
| **Workflow** | Secuencia de tareas multi-agente |
| **Planner** | Divide tareas complejas |
| **Orchestrator** | Coordina ejecución de tareas |
| **MCP** | Protocolo de comunicación con capa semántica |

## Próximos Pasos

Ahora que conoces los conceptos básicos:

1. [Crea tu primer proyecto](04-first-project.md)
2. [Crea tu primer agente](../single-agent/01-first-agent.md)

## Recursos

- [Arquitectura Completa](../reference/architecture.md)
- [Referencia CLI](../reference/cli-reference.md)
- [FAQ](../faq.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
