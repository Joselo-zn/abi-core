# ¿Por Qué Múltiples Agentes?

Aprende cuándo y por qué usar múltiples agentes en lugar de uno solo.

## El Problema con Un Solo Agente

Un agente que hace todo:
```
Agente Universal
├─ Analiza datos
├─ Escribe código
├─ Traduce idiomas
├─ Responde preguntas
├─ Genera reportes
└─ ... (hace todo mal)
```

**Problemas**:
- ❌ No es experto en nada
- ❌ Respuestas genéricas
- ❌ Difícil de mantener
- ❌ No escalable

## La Solución: Agentes Especializados

Múltiples agentes, cada uno experto:
```
Sistema Multi-Agente
├─ Agente Analista → Experto en análisis
├─ Agente Programador → Experto en código
├─ Agente Traductor → Experto en idiomas
└─ Agente Reportero → Experto en reportes
```

**Ventajas**:
- ✅ Cada agente es experto
- ✅ Respuestas especializadas
- ✅ Fácil de mantener
- ✅ Escalable

## Cuándo Usar Múltiples Agentes

### Caso 1: Tareas Complejas

**Tarea**: "Analiza ventas del último mes y genera un reporte en PDF"

**Con un agente**: Hace todo mal
**Con múltiples agentes**:
1. Agente Analista → Analiza ventas
2. Agente Reportero → Genera PDF

### Caso 2: Dominios Diferentes

**Proyecto**: Sistema de e-commerce

**Agentes necesarios**:
- Agente de Productos (catálogo)
- Agente de Ventas (transacciones)
- Agente de Soporte (ayuda al cliente)
- Agente de Inventario (stock)

### Caso 3: Escalabilidad

**Problema**: Un agente no da abasto

**Solución**: Múltiples instancias del mismo agente
```
Usuario 1 → Agente A
Usuario 2 → Agente B
Usuario 3 → Agente C
```

## Arquitectura Multi-Agente

```
Usuario
  ↓
Orchestrator (coordina)
  ↓
├─ Agente 1 (especialista)
├─ Agente 2 (especialista)
└─ Agente 3 (especialista)
  ↓
Resultado combinado
```

## Ejemplo Práctico

### Sistema de Análisis Financiero

```bash
# Crear proyecto
abi-core create project finanzas --with-semantic-layer

# Agente 1: Recolector de datos
abi-core add agent recolector \
  --description "Recolecta datos financieros"

# Agente 2: Analista
abi-core add agent analista \
  --description "Analiza datos financieros"

# Agente 3: Reportero
abi-core add agent reportero \
  --description "Genera reportes"
```

**Flujo**:
1. Usuario: "Analiza las acciones de Apple"
2. Recolector → Obtiene datos de Apple
3. Analista → Analiza los datos
4. Reportero → Genera reporte
5. Usuario recibe reporte completo

## Próximos Pasos

- [Agent Cards](02-agent-cards.md)
- [Comunicación entre agentes](03-agent-communication.md)
- [Tu primer sistema multi-agente](04-first-multi-agent-system.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
