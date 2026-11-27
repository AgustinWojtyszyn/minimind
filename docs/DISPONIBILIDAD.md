# BoitIA — acceso permanente sin suscripciones

## Estado de esta iteración

Se incorporó una edición estática de la interfaz existente, lista para publicar en GitHub Pages desde `master /docs`. La dirección esperada, **cuando Pages esté habilitado**, es https://agustinwojtyszyn.github.io/minimind/ . La publicación debe validarse en GitHub; no se afirma que ya esté operativa sin esa comprobación.

La interfaz usa el mismo esquema de almacenamiento, memoria, aprendizaje explícito y respaldo JSON. El origen web permanente mantiene los datos en el navegador aunque cambie el túnel de Kaggle. Para migrar, exporta desde Configuración en el origen anterior y después importa el JSON en el nuevo. No es sincronización entre dispositivos ni entrenamiento.

## Motor híbrido

1. Todos los visitantes leen el mismo registro público `engine.json` y seleccionan automáticamente el túnel del propietario si responde listo. No ingresan URLs ni tokens. Se reintenta incluso si el registro aún no tiene un motor. Si el motor está ocupado, se informa esa condición.
2. Si Kaggle no responde o está ocupado y hay otros motores registrados por el propietario, la página elige el respaldo Cloudflare, Modal, ZeroGPU y CPU en ese orden. Cloudflare, Modal y ZeroGPU no reciben sondeos periódicos: se inician al enviar una consulta. Si falla una solicitud posiblemente aceptada, no se reenvía automáticamente y se aplica un enfriamiento temporal del motor para el siguiente intento.
3. Si no hay ningún motor remoto disponible y el usuario autorizó la descarga de pesos local, la aplicación usa su dispositivo: Qwen2.5-1.5B-Instruct ONNX Q4 con WebGPU; si no es compatible, Qwen2.5-0.5B-Instruct ONNX Q4 con WASM/CPU. Un worker gestiona la generación para no bloquear la interfaz. El modelo local es inferior a 8B y puede ser lento, requerir almacenamiento y consumir batería. No se promete compatibilidad específica con todos los teléfonos.
4. Los endpoints de Cloudflare, Modal, ZeroGPU y CPU no se anuncian en el registro hasta que el propietario los despliegue y aprueben una consulta y CORS reales. No se adquieren créditos ni suscripciones automáticamente.

El motor propio Qwen3 continúa como primera opción. El respaldo Cloudflare utiliza Gemma 4 open-weight alojado por Cloudflare, no los pesos locales de BoitIA; nunca reemplaza ni modifica el motor propio. No hay un servidor GPU 24/7 ilimitado. Las descargas de pesos y dependencias necesitan Internet inicialmente; la caché del navegador puede ser eliminada y no garantiza operación completamente fuera de línea. La aplicación no reenvía automáticamente una consulta cuyo POST pudo haber sido aceptado: conserva el texto parcial o el prompt para reintento consciente. La recuperación puede elegir otro motor en la siguiente solicitud.

## Publicación del frontend

- Ajustes de [GitHub Pages](https://github.com/AgustinWojtyszyn/minimind/settings/pages): Build and deployment → Deploy from a branch → `master` → `/docs` → Save.
- No necesita un workflow personalizado ni un proveedor GPU contratado.
- Para actualizar el frontend, ejecuta `python scripts/build_portable.py` antes de versionar. La compilación deriva los archivos estáticos de la interfaz principal; no se mantienen dos diseños divergentes.
- Los pesos se descargan directamente a la caché del dispositivo por el runtime Transformers.js v3.8.1, no se incorporan a GitHub.

## Configuración única del propietario: motor compartido

El titular de la cuenta configura una credencial de GitHub una sola vez (renovarla cuando caduque). La página pública nunca recibe el secreto ni tiene un endpoint para modificar el registro.

1. Creá un [token de acceso personal fine-grained](https://github.com/settings/personal-access-tokens/new) autorizado sólo para el repositorio `AgustinWojtyszyn/minimind`, con permiso de repositorio **Contents: Read and write**. No seleccionar todos los repositorios ni compartir el token.
2. En Kaggle, Add-ons → Secrets, guardalo como `BOITIA_GITHUB_TOKEN` y habilitalo exclusivamente para el notebook privado del propietario. No pegarlo en una celda, en conversaciones o en el repositorio.
3. Detené el motor anterior y ejecutá esta única celda:

```python
from pathlib import Path
import subprocess, sys
repo = Path("/kaggle/working/boitia")
if not repo.exists():
    subprocess.run(["git","clone","--branch","master","https://github.com/AgustinWojtyszyn/minimind.git",str(repo)],check=True)
else:
    subprocess.run(["git","-C",str(repo),"pull","--ff-only","origin","master"],check=True)
subprocess.run([sys.executable,"-u",str(repo/"scripts/kaggle_shared.py")],cwd=repo,check=True)
```

El servidor valida conexión pública y CORS con el origen permanente antes de publicar exclusivamente la nueva URL en `docs/engine.json`, en `master`. No incluye credenciales, conversaciones ni otros datos. GitHub Pages actualizará el archivo cuando finalice su publicación. El cliente lee ese registro al abrir y cada 30 segundos; no usa viejos túneles guardados por visitante. Si una sesión de Kaggle termina, los visitantes verán indisponibilidad hasta que se registre un nuevo motor (o podrán activar, voluntariamente, el respaldo local). Esto no es una GPU dedicada 24/7. Las personas que ingresen no necesitan configurar nada ni mantener Kaggle abierto en sus propios dispositivos.

El registro tiene como valor inicial `null` para no inventar un túnel activo. No se habilita CORS general: sólo el origen HTTPS `https://agustinwojtyszyn.github.io` cuando el propietario autoriza el registro. El servidor de Kaggle conserva el modo del mismo origen si se inicia sin secreto. El inicio con secreto no falla si GitHub rechaza la publicación: se informa el problema sin mostrar la credencial.

## Cloudflare Workers AI — respaldo gratuito bajo demanda

Tras el bloqueo de elegibilidad de ZeroGPU, se añadió [deploy/cloudflare/README.md](../deploy/cloudflare/README.md). El motor compartido utiliza Gemma 4 26B A4B alojado por Cloudflare, con el prompt de BoitIA generado desde `boitia/config.py`. La página lo selecciona sólo si Kaggle no está disponible u ocupado. El plan **Workers Free** tiene 10.000 neuronas de inferencia diarias; se detiene al agotar la cuota. Debe confirmar el propietario que no hay Workers Paid antes de desplegar. No se cambia ni adquiere plan automáticamente. No es una instancia de GPU propia ni un reemplazo de Qwen. No requiere usuario, contraseña o descarga por parte de visitantes. Las consultas se envían al proveedor elegido, y la disponibilidad está sujeta a su cuota.

Despliegue desde WSL con Node.js y Python:

```bash
npx --yes wrangler@4 login
python scripts/deploy_cloudflare.py --apply --confirmed-free-plan
```

El script verifica una consulta anónima real y CORS antes de publicar. Si no tiene el token de GitHub en el entorno, imprime una URL verificada para registrarla una sola vez. El registro y el sitio no contienen credenciales.

## Activar ZeroGPU primero (sin método de pago si la cuenta es elegible)

Hugging Face permite hasta dos Spaces ZeroGPU en cuentas personales gratuitas elegibles (correo verificado y más de 30 días de antigüedad). La cuota anónima publicada es de 2 minutos de GPU al día; la del usuario gratuito autenticado, 5 minutos. No se eluden límites ni se garantiza capacidad. [ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu).

El motor en `deploy/zerogpu` reutiliza el código BoitIA con Qwen3-4B. En Kaggle **creá un notebook CPU separado** para no detener el motor actual. El propietario necesita un token de Hugging Face con permisos de escritura para crear su Space; guardalo como secreto `HF_TOKEN` y habilitá también el secreto existente `BOITIA_GITHUB_TOKEN` sólo en el notebook privado. Nunca pegar secretos en una celda o conversación.

```python
from pathlib import Path
import subprocess, sys
repo = Path("/kaggle/working/boitia")
if not repo.exists():
    subprocess.run(["git","clone","--branch","master","https://github.com/AgustinWojtyszyn/minimind.git",str(repo)],check=True)
else:
    subprocess.run(["git","-C",str(repo),"pull","--ff-only","origin","master"],check=True)
subprocess.run([sys.executable,"-u",str(repo/"scripts/kaggle_zerogpu.py")],cwd=repo,check=True)
```

El script crea únicamente ZeroGPU, sube el código público, espera a que termine la compilación, verifica una consulta sin credenciales de visitante y CORS para GitHub Pages, y registra la URL. No cambia la visibilidad ni el hardware de un Space existente; si ya existe, falla de forma segura. Si la cuenta no es elegible, la prueba falla o la cuota está agotada, no se publica una URL no probada. Tras el despliegue, el proceso Kaggle CPU puede detenerse.

## Modal y CPU Always Free (opcionales)

- [Modal](https://modal.com/pricing): Starter incluye crédito de cómputo; requiere método de pago y puede cobrar al superar créditos. **No desplegar antes de confirmar en el panel límites efectivos de gasto neto USD 0 y presupuesto dentro de créditos.** Ver [deploy/modal/README.md](../deploy/modal/README.md). El modelo Qwen3-8B NF4 utiliza una T4, una instancia máxima y escala a cero. El arranque y la ventana de inactividad también consumen recursos.
- [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm): la pequeña VM CPU sólo se provisionará si la cuenta tiene capacidad elegible y no habilita recursos pagos. El Dockerfile en `deploy/oracle` ejecuta llama.cpp con Qwen2.5-1.5B Q4, con uso de tokens estimado. Requiere HTTPS en el dominio del propietario `boitia.agustinwojtyszyn.com` y configuración DNS correspondiente; no está desplegado.

Para registrar cualquier motor ya desplegado, el script propietario `scripts/register_remote.py` verifica antes de modificar el registro, usa el secreto `BOITIA_GITHUB_TOKEN` y sólo acepta dominios de proveedores permitidos. Por defecto es simulación sin consultar ni modificar recursos. Ejemplos, tras verificar los límites:

```bash
python scripts/register_remote.py --provider modal --url https://TU-ENDPOINT.modal.run --apply --confirmed-zero-budget
python scripts/register_remote.py --provider cpu --url https://boitia.agustinwojtyszyn.com --apply
```

Se conserva la URL de Kaggle y las demás rutas al registrar una nueva. Si hay que retirar un motor, el titular puede poner su campo a `null` en `docs/engine.json` y detenerlo en el proveedor. Nunca registrar secretos ni APIs de modelos pagas. La página compartida no solicita descargas o tokens a los visitantes. Los recuerdos relevantes se envían sólo al motor seleccionado; los datos personales no se incluyen en el registro. No existe garantía de inferencia ilimitada gratuita.

## Pruebas

```bash
python -m unittest discover -s tests -v
node tests/ui_transport.test.cjs
node tests/ui_portable.test.cjs
node tests/ui_ondemand.test.cjs
node tests/ui_cloudflare.test.mjs
node tests/ui_markdown.test.cjs
python scripts/build_portable.py
python -m compileall -q boitia frontend deploy
```

Las pruebas locales cubren CORS opt-in, publicación de registro sin secretos, conexión automática de un visitante nuevo, rotación de túnel, respaldo local por consentimiento, validación de URL, persistencia existente y transporte. La inferencia real en Cloudflare, Modal, ZeroGPU y Oracle, sus presupuestos y compatibilidad externa requieren validación antes de registrar. GitHub Pages ya está configurado por el propietario; los motores nuevos no se dieron de alta desde el entorno de desarrollo.

## Actualización de arquitectura · noviembre 2026

La prioridad actual del cliente público es Cloudflare → Kaggle → Modal → ZeroGPU → CPU.
Solo se seleccionan URL presentes en el registro; el respaldo local se habilita mediante
«activar motor local» y se descarga únicamente al necesitarlo, con consentimiento.
El código de Cloudflare 3036 suspende ese endpoint hasta las 00:00 UTC en ese navegador;
otros errores recuperables se enfrían durante 60 segundos. No equivale a una lectura
global de cuotas de la cuenta. Cada consulta puede realizar como máximo un reintento
en otro motor, y reemplaza el texto parcial solo al recibir una respuesta completa.
El cliente registra proveedor, duración, intento y estado técnico (sin contenido de la conversación).

### Conocimientos documentales locales

Adjuntá un archivo compatible y escribí «Aprendé de este documento y utilizalo en futuras conversaciones».
El texto se extrae localmente, se conserva en el perfil del navegador y se recuperan
hasta tres fragmentos relevantes por consulta mediante coincidencias léxicas; las citas [D1],
[D2] y [D3] identifican los documentos recuperados. No es entrenamiento neuronal ni
sincronización por cuenta. No compartas el perfil del navegador si querés mantener
los documentos privados. Solo los fragmentos necesarios se incluyen en solicitudes al motor.
«Mostrame mis documentos» lista los archivos; «Olvidá el documento 1» elimina el conocimiento.
Volver a aprender un archivo con el mismo nombre actualiza su contenido. El respaldo JSON
incluye los conocimientos locales (puede contener información privada).
Los límites de esta versión son 20 documentos, 100.000 caracteres por documento,
500.000 caracteres totales, 60 páginas de PDF de texto y hasta 500 filas de la primera hoja
de XLSX. La extracción de documentos y estadísticas no ejecuta macros o fórmulas.

### Entrenamiento neuronal: ejecución privada y versionada

El entrenamiento QLoRA requiere un dataset JSONL autorizado y la lista de hashes de los
pares pregunta/respuesta revisados por el propietario. No se incorporan automáticamente
conversaciones ni documentos aprendidos al dataset. Cada ejecución exige un directorio
nuevo (por ejemplo, una versión bajo /kaggle/working) y guarda un manifiesto de modelos,
datos y configuración, una evaluación previa, checkpoints y un reporte con el digest
del adaptador. La reanudación verifica esos datos y selecciona el checkpoint completo
más reciente. El entrenamiento multi-GPU es optativo mediante torchrun con dos procesos,
cada uno con una réplica NF4 en una GPU; no aumenta la VRAM disponible para un modelo
individual. La viabilidad y el rendimiento en dos T4 deben medirse en Kaggle.
El mejor modelo de validación y la detención temprana (para múltiples épocas) ayudan
a reducir sobreajuste, pero la promoción requiere además la evaluación independiente
existente y aprobación explícita; no se activa ningún candidato automáticamente.
El comando de rollback verifica el digest del adaptador anterior antes de cambiar el
puntero activo. Para persistencia entre sesiones Kaggle deben conservarse los outputs
privados de la ejecución — los checkpoints locales no garantizan persistencia tras
perder la sesión. No se ha ejecutado ni certificado entrenamiento T4 en esta iteración.
