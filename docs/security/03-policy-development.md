# Desarrollo de Políticas

Crea políticas personalizadas para tu dominio.

## Crear Política

```bash
abi-core add policies trading --domain finance
```

Esto crea:
```
services/guardian/opa/policies/trading.rego
```

## Estructura de Política

```rego
package abi.trading

# Regla por defecto
default allow = false

# Permitir trades pequeños
allow if {
    input.action == "execute_trade"
    input.amount < 1000
}

# Requerir aprobación para trades medianos
require_approval if {
    input.action == "execute_trade"
    input.amount >= 1000
    input.amount < 10000
}

# Denegar trades grandes
deny["Monto excede límite máximo"] if {
    input.action == "execute_trade"
    input.amount >= 10000
}
```

## Próximos Pasos

- [Auditoría y compliance](04-audit-compliance.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
