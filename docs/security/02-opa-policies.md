# Políticas con OPA

OPA (Open Policy Agent) evalúa políticas de seguridad en tiempo real.

## ¿Qué es OPA?

OPA es un motor de políticas que decide:
- ¿Puede este agente hacer esta acción?
- ¿Cumple con las reglas de negocio?
- ¿Es seguro proceder?

## Ejemplo de Política

```rego
package abi.custom

# Permitir solo en horario laboral
allow if {
    input.action == "execute_trade"
    time.now_ns() >= business_hours_start
    time.now_ns() <= business_hours_end
}

# Denegar transacciones grandes
deny["Monto excede límite"] if {
    input.action == "execute_trade"
    input.amount > 10000
}
```

## Probar Política

```bash
curl -X POST http://localhost:8181/v1/data/abi/custom \
  -d '{
    "input": {
      "action": "execute_trade",
      "amount": 5000
    }
  }'
```

## Próximos Pasos

- [Desarrollo de políticas](03-policy-development.md)

---

**Creado por [José Luis Martínez](https://github.com/Joselo-zn)** | jl.mrtz@gmail.com
