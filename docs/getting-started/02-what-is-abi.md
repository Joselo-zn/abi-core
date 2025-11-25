# ¿Qué es ABI-Core?

ABI-Core es un framework para construir **sistemas de agentes de IA** que pueden trabajar juntos de forma inteligente y segura.

## La Idea Simple

Imagina que tienes varios asistentes de IA, cada uno especializado en algo diferente:

- 🤖 Un agente que **analiza datos**
- 🤖 Un agente que **escribe reportes**
- 🤖 Un agente que **responde preguntas**

**ABI-Core** te permite:

1. **Crear** estos agentes fácilmente
2. **Conectarlos** para que trabajen juntos
3. **Descubrirlos** automáticamente cuando los necesites
4. **Protegerlos** con políticas de seguridad

## ¿Por Qué Usar ABI-Core?

### Sin ABI-Core

```python
# Tienes que hacer todo manualmente
llm = ChatOllama(model="qwen2.5:3b")
response = llm.invoke("Analiza estos datos...")

# ¿Cómo conectar con otro agente?
# ¿Cómo saber qué agentes existen?
# ¿Cómo aplicar seguridad?
# Todo es complicado...
```

### Con ABI-Core

```bash
# Crear un proyecto
abi-core create project mi-sistema

# Agregar un agente
abi-core add agent analista --description "Analiza datos"

# Iniciar todo
abi-core run

# ¡Listo! Tu agente está funcionando
```

## Componentes Principales

### 1. Agentes 🤖

Los **agentes** son programas de IA que pueden:

- Entender lenguaje natural
- Ejecutar tareas específicas
- Usar herramientas (calculadoras, APIs, bases de datos)
- Comunicarse con otros agentes

**Ejemplo**: Un agente que responde preguntas sobre productos.

### 2. Capa Semántica 🧠

La **capa semántica** es como un directorio inteligente que:

- Sabe qué agentes existen
- Entiende qué puede hacer cada agente
- Encuentra el agente correcto para cada tarea

**Ejemplo**: Cuando preguntas "¿Quién puede analizar ventas?", la capa semántica encuentra al agente de análisis.

### 3. Seguridad 🔒

El **Guardian** es el sistema de seguridad que:

- Controla quién puede hacer qué
- Registra todas las acciones
- Aplica políticas de cumplimiento

**Ejemplo**: Solo el agente de finanzas puede ejecutar transacciones.

### 4. Orquestación 🎭

El **Orchestrator** coordina múltiples agentes:

- Divide tareas complejas en subtareas
- Asigna cada subtarea al agente correcto
- Combina los resultados

**Ejemplo**: "Analiza ventas y genera reporte" → Agente de análisis + Agente de reportes.

## Arquitectura Visual

```
┌─────────────────────────────────────────────────────────┐
│                    Tu Aplicación                        │
│                  (Web, API, CLI)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                  Orchestrator                           │
│         (Coordina múltiples agentes)                    │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ↓           ↓           ↓
    ┌────────┐  ┌────────┐  ┌────────┐
    │Agente 1│  │Agente 2│  │Agente 3│
    │Analista│  │Escritor│  │Buscador│
    └────────┘  └────────┘  └────────┘
         │           │           │
         └───────────┼───────────┘
                     ↓
         ┌───────────────────────┐
         │   Capa Semántica      │
         │ (Descubre agentes)    │
         └───────────────────────┘
                     │
                     ↓
         ┌───────────────────────┐
         │      Guardian         │
         │  (Seguridad y logs)   │
         └───────────────────────┘
```

## Casos de Uso

### 1. Chatbot Inteligente

Un chatbot que puede:
- Responder preguntas
- Buscar información
- Ejecutar acciones

```bash
abi-core create project chatbot
abi-core add agent asistente --description "Chatbot de ayuda"
```

### 2. Sistema de Análisis

Múltiples agentes que:
- Recolectan datos
- Analizan tendencias
- Generan reportes

```bash
abi-core create project analisis --with-semantic-layer
abi-core add agent recolector --description "Recolecta datos"
abi-core add agent analizador --description "Analiza datos"
abi-core add agent reportero --description "Genera reportes"
```

### 3. Asistente Empresarial

Sistema completo con:
- Múltiples agentes especializados
- Descubrimiento automático
- Seguridad y auditoría

```bash
abi-core create project empresa \
  --with-semantic-layer \
  --with-guardian
```

## Ventajas de ABI-Core

### ✅ Fácil de Usar

```bash
# 3 comandos y tienes un agente funcionando
abi-core create project mi-app
abi-core add agent mi-agente
abi-core run
```

### ✅ Escalable

- Empieza con 1 agente
- Crece a 10, 100 o más
- Los agentes se descubren automáticamente

### ✅ Seguro

- Políticas de acceso
- Auditoría completa
- Cumplimiento normativo

### ✅ Flexible

- Usa cualquier modelo de IA (Ollama, OpenAI, etc.)
- Integra con tus sistemas existentes
- Personaliza todo

## Tecnologías Incluidas

ABI-Core integra las mejores herramientas:

- **LangChain**: Framework de IA
- **Ollama**: Modelos de IA locales
- **Weaviate**: Base de datos vectorial
- **OPA**: Motor de políticas
- **FastAPI**: APIs web
- **Docker**: Contenedores

## Filosofía de ABI

ABI-Core se basa en tres principios:

### 1. Interoperabilidad Semántica

Los agentes deben compartir **significado**, no solo datos.

**Mal**: Enviar `{"data": [1,2,3]}`  
**Bien**: Enviar `{"ventas_mensuales": [1000, 2000, 3000], "moneda": "USD"}`

### 2. Inteligencia Distribuida

Ningún modelo tiene toda la verdad. La colaboración es clave.

**Mal**: Un solo agente hace todo  
**Bien**: Múltiples agentes especializados colaboran

### 3. Autonomía Gobernada

Los agentes son autónomos pero con límites claros.

**Mal**: Agentes sin restricciones  
**Bien**: Agentes con políticas de seguridad

## Próximos Pasos

Ahora que entiendes qué es ABI-Core, aprende:

1. [Conceptos Básicos](03-basic-concepts.md) - Términos y conceptos clave
2. [Tu Primer Proyecto](04-first-project.md) - Crea tu primer sistema

## Recursos

- [Ejemplos en GitHub](https://github.com/Joselo-zn/abi-core/tree/main/examples)
- [Arquitectura Detallada](../reference/architecture.md)
- [FAQ](../faq.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
