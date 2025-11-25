# ABI-Core Documentation

Bienvenido a la documentación de **ABI-Core** — un framework completo para construir sistemas de agentes de IA con capas semánticas, orquestación y políticas de seguridad.

```{toctree}
:maxdepth: 2
:caption: 1. Fundamentos

getting-started/01-installation
getting-started/02-what-is-abi
getting-started/03-basic-concepts
getting-started/04-first-project
```

```{toctree}
:maxdepth: 2
:caption: 2. Agentes Individuales

single-agent/01-first-agent
single-agent/02-simple-chatbot
single-agent/03-agents-with-tools
single-agent/04-agents-with-memory
single-agent/05-testing-agents
```

```{toctree}
:maxdepth: 2
:caption: 3. Múltiples Agentes

multi-agent-basics/01-why-multiple-agents
multi-agent-basics/02-agent-cards
multi-agent-basics/03-agent-communication
multi-agent-basics/04-first-multi-agent-system
```

```{toctree}
:maxdepth: 2
:caption: 4. Capa Semántica

semantic-layer/01-what-is-semantic-layer
semantic-layer/02-agent-discovery
semantic-layer/03-semantic-search
semantic-layer/04-extending-semantic-layer
```

```{toctree}
:maxdepth: 2
:caption: 5. Orquestación Avanzada

orchestration/01-planner-orchestrator
orchestration/02-multi-agent-workflows
orchestration/03-dependency-management
orchestration/04-result-synthesis
```

```{toctree}
:maxdepth: 2
:caption: 6. RAG y Conocimiento

rag/01-what-is-rag
rag/02-vector-databases
rag/03-embeddings-search
rag/04-agents-with-rag
```

```{toctree}
:maxdepth: 2
:caption: 7. Seguridad y Políticas

security/01-guardian-service
security/02-opa-policies
security/03-policy-development
security/04-audit-compliance
```

```{toctree}
:maxdepth: 2
:caption: 8. Producción

production/01-model-serving
production/02-monitoring-logs
production/03-troubleshooting
production/04-deployment
```

```{toctree}
:maxdepth: 2
:caption: 9. Referencia

reference/cli-reference
reference/api-reference
reference/environment-variables
reference/architecture
```

```{toctree}
:maxdepth: 1
:caption: Recursos Adicionales

changelog
faq
roadmap
```

## ¿Qué es ABI-Core?

**ABI-Core** (Agent-Based Infrastructure Core) es un framework de producción que combina:

- 🤖 **Agentes de IA** — Agentes potenciados por LangChain con comunicación A2A
- 🧠 **Capa Semántica** — Embeddings vectoriales y gestión de conocimiento distribuido
- 🔒 **Seguridad** — Aplicación de políticas basada en OPA y control de acceso
- 🌐 **Interfaces Web** — APIs REST basadas en FastAPI y dashboards en tiempo real
- 📦 **Contenedorización** — Despliegues listos para Docker con orquestación

## Inicio Rápido

```bash
# Instalar ABI-Core
pip install abi-core-ai

# Crear tu primer proyecto
abi-core create project mi-sistema-ia --with-semantic-layer

# Navegar al proyecto
cd mi-sistema-ia

# Provisionar modelos
abi-core provision-models

# Crear un agente
abi-core add agent mi-agente --description "Mi primer agente de IA"

# Iniciar el sistema
abi-core run
```

## Rutas de Aprendizaje

### 🎯 Para Principiantes
1. [Instalación](getting-started/01-installation.md)
2. [¿Qué es ABI-Core?](getting-started/02-what-is-abi.md)
3. [Tu Primer Proyecto](getting-started/04-first-project.md)
4. [Tu Primer Agente](single-agent/01-first-agent.md)

### 🚀 Para Desarrolladores
1. [Agentes con Herramientas](single-agent/03-agents-with-tools.md)
2. [Comunicación Entre Agentes](multi-agent-basics/03-agent-communication.md)
3. [Capa Semántica](semantic-layer/01-what-is-semantic-layer.md)
4. [Workflows Multi-Agente](orchestration/02-multi-agent-workflows.md)

### 🏢 Para Producción
1. [Model Serving](production/01-model-serving.md)
2. [Seguridad con Guardian](security/01-guardian-service.md)
3. [Monitoreo y Logs](production/02-monitoring-logs.md)
4. [Deployment](production/04-deployment.md)

## Comunidad y Soporte

- **GitHub**: [github.com/Joselo-zn/abi-core](https://github.com/Joselo-zn/abi-core)
- **Issues**: [Reportar bugs o solicitar features](https://github.com/Joselo-zn/abi-core/issues)
- **Discussions**: [Únete a la conversación](https://github.com/Joselo-zn/abi-core/discussions)
- **Email**: jl.mrtz@gmail.com

## Licencia

ABI-Core se distribuye bajo la Licencia Apache 2.0. Ver [LICENSE](https://github.com/Joselo-zn/abi-core/blob/main/LICENSE) para detalles.

---

**Construido con ❤️ por [José Luis Martínez](https://github.com/Joselo-zn)**  
Creador de **ABI (Agent-Based Infrastructure)** — redefiniendo cómo los sistemas inteligentes se interconectan.
