# Búsqueda Semántica

La búsqueda semántica encuentra agentes por significado, no solo por palabras exactas.

## Búsqueda por Palabras vs Semántica

### Búsqueda por Palabras
```
Buscar: "analizar ventas"
Encuentra: Solo agentes con "analizar" Y "ventas"
```

### Búsqueda Semántica
```
Buscar: "examinar ingresos"
Encuentra: Agente de análisis de ventas
(Entiende que "examinar" ≈ "analizar" e "ingresos" ≈ "ventas")
```

## Cómo Funciona

1. Texto → Embeddings (vectores numéricos)
2. Búsqueda por similitud vectorial
3. Retorna agentes más relevantes

## Usar Búsqueda Semántica

```python
# Diferentes formas de pedir lo mismo
await client.find_agent(session, "analizar datos de ventas")
await client.find_agent(session, "examinar información de ingresos")
await client.find_agent(session, "revisar estadísticas comerciales")
# Todos encuentran el mismo agente
```

## Próximos Pasos

- [Extender capa semántica](04-extending-semantic-layer.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
