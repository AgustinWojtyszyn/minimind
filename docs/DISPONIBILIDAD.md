# BoitIA — acceso permanente sin suscripciones

## Estado de esta iteración

Se incorporó una edición estática de la interfaz existente, lista para publicar en GitHub Pages desde `master /docs`. La dirección esperada, **cuando Pages esté habilitado**, es https://agustinwojtyszyn.github.io/minimind/ . La publicación debe validarse en GitHub; no se afirma que ya esté operativa sin esa comprobación.

La interfaz usa el mismo esquema de almacenamiento, memoria, aprendizaje explícito y respaldo JSON. El origen web permanente mantiene los datos en el navegador aunque cambie el túnel de Kaggle. Para migrar, exporta desde Configuración en el origen anterior y después importa el JSON en el nuevo. No es sincronización entre dispositivos ni entrenamiento.

## Motor híbrido

1. Si el propietario configura el túnel HTTPS de Kaggle y éste responde listo y no ocupado, BoitIA lo elige de forma preferente.
2. Si no está disponible y el usuario autorizó la descarga de pesos local, la aplicación usa su dispositivo: Qwen2.5-1.5B-Instruct ONNX Q4 con WebGPU; si no es compatible, Qwen2.5-0.5B-Instruct ONNX Q4 con WASM/CPU. Un worker gestiona la generación para no bloquear la interfaz. El modelo local es inferior a 8B y puede ser lento, requerir almacenamiento y consumir batería. No se promete compatibilidad específica con todos los teléfonos.
3. El prototipo ZeroGPU se prepara como Space Gradio separado, pendiente de despliegue y pruebas reales antes de incorporarlo al selector automático. Usa Qwen3-4B, FP16 y una reserva GPU bajo demanda limitada. No se adquieren créditos ni suscripciones.

No se usan API comerciales en sustitución de los pesos locales. No hay un servidor GPU 24/7 ilimitado. Las descargas de pesos y dependencias necesitan Internet inicialmente; la caché del navegador puede ser eliminada y no garantiza operación completamente fuera de línea. La aplicación no reenvía automáticamente una consulta cuyo POST pudo haber sido aceptado: conserva el texto parcial o el prompt para reintento consciente. La recuperación puede elegir otro motor en la siguiente solicitud.

## Publicación del frontend

- Ajustes de [GitHub Pages](https://github.com/AgustinWojtyszyn/minimind/settings/pages): Build and deployment → Deploy from a branch → `master` → `/docs` → Save.
- No necesita un workflow personalizado ni un proveedor GPU contratado.
- Para actualizar el frontend, ejecuta `python scripts/build_portable.py` antes de versionar. La compilación deriva los archivos estáticos de la interfaz principal; no se mantienen dos diseños divergentes.
- Los pesos se descargan directamente a la caché del dispositivo por el runtime Transformers.js v3.8.1, no se incorporan a GitHub.

## Conexión de Kaggle desde el dominio permanente

En la celda de inicio de Kaggle, antes de iniciar el servidor:

```python
import os
os.environ["BOITIA_PORTABLE_ORIGIN"] = "https://agustinwojtyszyn.github.io"
```

Inicia la última versión de `master` usando el procedimiento de [BOITIA.md](BOITIA.md). En la URL de Pages, abre Configuración y pega la URL raíz nueva del túnel. El servidor mantiene mismo origen por defecto; CORS sólo se permite para el origen HTTPS explícito del propietario, sin credenciales ni comodines. No hay API que acepte destinos arbitrarios en el servidor. Los mensajes y recuerdos relevantes se envían al motor Kaggle que el usuario configuró; en modo local se procesan en el dispositivo.

## ZeroGPU — creación opcional en una cuenta elegible

Los requisitos actuales de Hugging Face permiten hasta dos Spaces ZeroGPU en cuentas personales gratuitas elegibles (correo verificado y más de 30 días de antigüedad), con cuota de GPU por usuario. See [ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu). No crear un Space de CPU/Docker pago: [reglas de creación](https://huggingface.co/docs/hub/spaces-overview).

El prototipo está en `deploy/zerogpu`, reutiliza el prompt y la generación de BoitIA a través de Gradio. Para desplegar, el propietario debe tener un token de Hugging Face con permisos de escritura, guardado como secreto `HF_TOKEN` en el entorno privado. Nunca pegarlo en Git, frontend, conversación ni notebook público. El siguiente comando exige confirmación explícita mediante `--apply`, sólo solicita ZeroGPU (identificador histórico `zero-a10g`) y no actualiza hardware ni crea recursos pagos. Si el nombre ya existe, falla sin sobrescribirlo.

```bash
python scripts/deploy_zerogpu.py
python scripts/deploy_zerogpu.py --apply
```

El Space creado es público, sólo contiene código público y pesos abiertos; no sube conversaciones, secretos, datos ni adaptadores. La cola y cuotas oficiales aplican; no se eluden. Antes de conectar al frontend, probar la carga real y la API `/complete`. Si la cuenta no es elegible, detener el despliegue sin cambiar a un plan pago.

## Pruebas

```bash
python -m unittest discover -s tests -v
node tests/ui_transport.test.cjs
node tests/ui_portable.test.cjs
python scripts/build_portable.py
python -m compileall -q boitia frontend deploy
```

Las pruebas locales cubren CORS opt-in, prioridad Kaggle, respaldo local por consentimiento, validación de URL, persistencia existente y transporte. La descarga/ejecución neuronal real, compatibilidad del móvil, activación de Pages y funcionamiento de ZeroGPU requieren validación externa.
