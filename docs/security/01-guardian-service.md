# Guardian Service

Guardian es el servicio de seguridad que protege tu sistema de agentes.

## ¿Qué Hace Guardian?

- 🔒 Control de acceso
- 📝 Auditoría de acciones
- ⚠️ Alertas de seguridad
- 📊 Dashboard de monitoreo

## Agregar Guardian

```bash
abi-core create project mi-app --with-guardian
```

O agregar a proyecto existente:
```bash
abi-core add service guardian-native
```

## Componentes

### 1. Guardian Agent
Monitorea y aplica políticas.

### 2. OPA (Open Policy Agent)
Motor de evaluación de políticas.

### 3. Dashboard
Interfaz web para monitoreo.

## Acceder al Dashboard

```
http://localhost:8080
```

## Próximos Pasos

- [Políticas con OPA](02-opa-policies.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
