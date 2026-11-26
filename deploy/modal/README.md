# Modal: GPU bajo demanda (NO desplegar hasta verificar límite de gasto)

Usa el mismo Qwen3-8B NF4 y la API de BoitIA. La T4 se arranca sólo para consultas, con una instancia máxima y 10 s de ventana de reducción a cero; ese tiempo y los arranques también consumen créditos. No sondea el motor periódicamente. Requiere cuenta, credenciales de Modal y método de pago según las condiciones actuales.

**El plan Starter tiene crédito mensual, pero es de pago por uso si se excede.** Verificar en Usage & Billing un límite neto USD 0 efectivo y presupuesto bruto dentro de los créditos. No activar si no es posible. No usar Model APIs de Modal.

Con las credenciales de Modal ya configuradas, desde el repositorio:

```bash
python -m pip install modal
python scripts/deploy_modal.py --apply --confirmed-zero-budget
```

El despliegue puede consumir créditos para preparación/arranque; verificar primero la configuración de facturación. Registrar sólo después de confirmar que el gasto permanece dentro de créditos, con el verificador del propietario `scripts/register_remote.py` (ver docs/DISPONIBILIDAD.md). El propietario puede detener el app en Modal y eliminar la URL del registro. No se mantiene GPU despierta artificialmente. La disponibilidad y la latencia no están verificadas hasta una prueba real.
