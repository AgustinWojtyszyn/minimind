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

El Worker no es un servicio GPU reservado: las consultas consumen la cuota de inferencia, no hay un proceso de Kaggle que mantener activo. El health check no llama a AI. La respuesta JSON se transforma a la interfaz de BoitIA sin mostrar metadatos internos de razonamiento. Su generación no es progresiva en este perfil inicial; el frontend indica que está trabajando. Las métricas y la calidad deben verificarse en el despliegue real.

## Alternativa HTTPS si workers.dev no emite certificado

En Cloudflare Dashboard, Workers & Pages → boitia-ai → Domains (o Settings → Domains & Routes) → Add → Custom Domain. Agregar únicamente `boitia-ai.agustinwojtyszyn.com` si está libre; no cambiar registros existentes del dominio principal ni aceptar una compra. Una vez que el certificado esté activo, probar el motor mediante `verify_remote("cloudflare","https://boitia-ai.agustinwojtyszyn.com")`. Sólo publicar la URL en el registro cuando pase la prueba. No desactivar HTTPS ni la validación de certificados.
