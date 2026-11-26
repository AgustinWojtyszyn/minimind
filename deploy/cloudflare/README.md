# BoitIA Cloudflare — motor compartido de respaldo

El Worker utiliza un modelo abierto **Gemma 4 26B A4B** alojado por Cloudflare. No es el modelo entrenado/controlado localmente, no reemplaza Qwen3-8B en Kaggle y no cambia sus pesos. Sólo se selecciona cuando Kaggle no responde o está ocupado. Usa el prompt de personalidad oficial generado de `boitia/config.py`, sin herramientas, APIs externas arbitrarias ni almacenamiento de conversaciones.

Cloudflare Workers **Free** incluye 10.000 neuronas de inferencia por día, compartidas en la cuenta, y devuelve error cuando se agotan. [Precios oficiales](https://developers.cloudflare.com/workers-ai/platform/pricing/). NO habilitar Workers Paid, créditos o AI Gateway de pago. No se garantiza disponibilidad ilimitada. Los mensajes y recuerdos seleccionados para la consulta se procesan en Cloudflare. El endpoint solicita sólo el origen web del propietario (CORS no es autenticación); aplica límites locales aproximados por IP, límite de entrada y de salida, y depende del límite gratuito de la cuenta.

## Despliegue único desde WSL/terminal del propietario

1. Abrir https://dash.cloudflare.com/ y crear/acceder a la cuenta gratuita. Verificar que **Workers Free** está activo.
2. Desde la raíz del repo actualizado, ejecutar:

```bash
npx --yes wrangler@4 login
python scripts/deploy_cloudflare.py --apply --confirmed-free-plan
```

El script instala Wrangler con npx, genera el prompt actualizado, despliega únicamente el Worker `boitia-ai`, verifica CORS y realiza una consulta real pequeña. No solicita pagar; si Cloudflare requiere upgrade, cancelar y no modificar el plan. El propietario acepta la autenticación OAuth de Wrangler desde su equipo y elige su cuenta si aparece más de una. No incluir credenciales en GitHub.

Cuando imprima `Cloudflare verificado`, la URL estable será `https://boitia-ai.<subdominio>.workers.dev`. Si el secreto BOITIA_GITHUB_TOKEN existe ya en el entorno, el script publica la URL; de lo contrario, comunicar sólo la URL verificada al administrador para registrarla en `docs/engine.json`. No se debe publicar una URL no probada. El registro conserva Kaggle y las demás rutas. Si el respaldo debe retirarse, poner `cloudflare_url` a `null` y detener el Worker. Los visitantes no necesitan cuenta, token ni descargas.

El Worker no es un servicio GPU reservado: las consultas consumen la cuota de inferencia, no hay un proceso de Kaggle que mantener activo. El health check no llama a AI. La respuesta JSON se transforma a la interfaz de BoitIA sin mostrar metadatos internos de razonamiento. El Worker admite streaming SSE cuando el cliente lo solicita (y conserva JSON para clientes anteriores). La interfaz muestra texto progresivamente, conserva respuestas parciales y no reenvía automáticamente una consulta interrumpida. El fallback Cloudflare evita esperar más de 1,5 segundos por un Kaggle sin respuesta al comprobar disponibilidad. Las métricas y la calidad deben verificarse en el despliegue real.

## Alternativa HTTPS si workers.dev no emite certificado

En Cloudflare Dashboard, Workers & Pages → boitia-ai → Domains (o Settings → Domains & Routes) → Add → Custom Domain. Agregar únicamente `boitia-ai.agustinwojtyszyn.com` si está libre; no cambiar registros existentes del dominio principal ni aceptar una compra. Una vez que el certificado esté activo, probar el motor mediante `verify_remote("cloudflare","https://boitia-ai.agustinwojtyszyn.com")`. Sólo publicar la URL en el registro cuando pase la prueba. No desactivar HTTPS ni la validación de certificados.


## Presupuestos de salida
Rápido 8.192, Equilibrado 32.768 y Profundo 128.000 tokens son máximos configurados por solicitud, no cantidades garantizadas por el proveedor. Gemma documenta una ventana de contexto de 256K, que no equivale a una salida garantizada. Las respuestas breves terminan antes de alcanzar su máximo. Cloudflare puede aplicar límites efectivos inferiores, tiempos de espera y su cuota gratuita diaria; no se contrata capacidad adicional. La interfaz aguarda hasta 10 minutos en la solicitud, pero ese tiempo no amplía el límite del proveedor. Los tres máximos aparecen en /health para verificar la versión activa.

## Latencia: verificación real
Con el Worker actualizado, `/health` indica `transport: "sse"` y `worker_revision: "cf-inference-5"`. El cliente solicita streaming; la velocidad neuronal sigue dependiendo del proveedor. Comparar tiempo hasta el primer fragmento de contenido y tiempo total sobre la misma consulta y modo; el comentario SSE inicial no cuenta como token generado.

## Modo rápido conversacional (prompt 2.3)
El modo rápido aplica una pauta de brevedad de 40–100 palabras para consultas cotidianas, sin un nuevo límite duro de tokens; las solicitudes de detalle, código y justificación conservan su presupuesto. Se adapta al español rioplatense. Los modos equilibrado y profundo no reciben esta pauta de brevedad. El revisionado del Worker ahora es `cf-inference-6`.

Para medir una consulta real desde WSL antes y después del despliegue:

```bash
python3 scripts/benchmark_cloudflare.py
```

Cada ejecución consume una solicitud de la cuota gratuita; informa tiempo al primer texto visible, tiempo total, palabras y caracteres, no una estimación de tokens/s. La calidad y latencia dependen del proveedor; no se prometen siete segundos.

### Actualizaciones sin token manual (OAuth)
Desde WSL, con Workers Free y la cuenta correcta, iniciá sesión mediante el flujo de dispositivo (sin localhost):

```bash
unset CLOUDFLARE_API_TOKEN
npx --yes wrangler@4.168.0 login --device --browser=false
```

Abrí en Chrome el enlace impreso por Wrangler y autorizá tu propia cuenta. La credencial OAuth se guarda localmente por Wrangler; no la incluyas en el repositorio. Luego, en la raíz del repo actualizado:

```bash
export CLOUDFLARE_ACCOUNT_ID="e46fabce5acf65563e13e8c946af64b8"
python3 scripts/update_cloudflare.py --oauth --confirmed-free-plan
```

No crea un Worker nuevo ni modifica rutas, dominios o plan. Las próximas actualizaciones pueden reutilizar la sesión mientras siga válida; si expira, repetí el login.
