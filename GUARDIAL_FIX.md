# Fix para Error de Sintaxis en guardial.py

## Problema:
Línea 575-576 en `abi-core/agents/guardial/agent/guardial.py`:

```python
# Alias for backward compatibility
AbiGuardianSecure = AbiGuardianSecure
    async def validate_emergency_integrity(self) -> Dict[str, Any]:  # ← MAL INDENTADO
```

## Solución:
Mover la función dentro de la clase antes del método `close()`:

```python
    async def close(self):
        """Cleanup resources"""
        await self.policy_engine.close()

    async def validate_emergency_integrity(self) -> Dict[str, Any]:
        """
        Validate integrity of emergency event logs
        
        Returns:
            Emergency log integrity validation results
        """
        return await self.emergency_system.validate_emergency_integrity()

# Alias for backward compatibility (al final del archivo)
AbiGuardianSecure = AbiGuardianSecure
```

## Comando para aplicar:
```bash
# Editar el archivo y mover la función validate_emergency_integrity 
# dentro de la clase AbiGuardianSecure, antes del método close()
```