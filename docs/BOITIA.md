# BoitIA — arquitectura y operación

Para la URL permanente, modo local del navegador y prototipo ZeroGPU, consulta [Disponibilidad](DISPONIBILIDAD.md).

## Lanzamiento de Kaggle

Activa GPU e Internet si la sesión lo permite. Para migrar desde un notebook con pesos antiguos cargados, reinicia el kernel **sin borrar el almacenamiento**; no basta con detener el túnel si otro objeto Python conserva VRAM. Ejecuta una única celda:

```python
from pathlib import Path
import subprocess, sys
repo = Path('/kaggle/working/boitia')
if not repo.exists():
    subprocess.run(['git','clone','--branch','master','--depth','1','https://github.com/AgustinWojtyszyn/minimind.git',str(repo)],check=True)
else:
    subprocess.run(['git','-C',str(repo),'pull','--ff-only','origin','master'],check=True)
import os
os.environ.setdefault('BOITIA_MODEL','Qwen/Qwen3-8B')
state=Path('/kaggle/working/boitia-state')
requirements='requirements-boitia-train.txt' if (state/'active.json').is_file() else 'requirements-boitia.txt'
subprocess.run([sys.executable,'-m','pip','install','-q','-r',str(repo/requirements)],check=True)
subprocess.run([sys.executable,'-u',str(repo/'frontend/boitia_server.py')],cwd=repo,check=True)
```

La celda queda ejecutándose para mantener el proceso vivo. El servidor verifica una generación neuronal real antes de abrir el túnel; comprueba `/health` local y público. Sólo entonces anuncia la URL. Para detenerlo, interrumpe la celda. La URL es temporal y la sesión está sujeta a límites y reglas de Kaggle y Cloudflare Quick Tunnels. No hay garantía de servicio continuo. No se piden tokens a visitantes. El modelo se descarga de Hugging Face con Internet habilitado; no se reinstala PyTorch. Para forzar un candidato de la lista, el propietario puede definir `BOITIA_MODEL` en el entorno; `BOITIA_CACHE` permite indicar un cache disponible. El lanzador no borra otros modelos ni datos. Antes de reiniciar, exporta el espacio de trabajo desde Configuración (un nuevo Quick Tunnel cambia el origen del almacenamiento). La configuración predeterminada usa 8B; un candidato explícito fallido recupera 8B cuando sea posible.

## Motor y candidatos

Arquitectura: navegador → FastAPI de mismo origen → validación y límite de concurrencia → motor PyTorch/Transformers → pesos cuantizados distribuidos por Accelerate. Reserva nominal de 3 GiB por GPU, FP16 para Turing y SDPA (no FlashAttention 2 obligatoria ni BF16). La cuantización NF4 doble reduce memoria de pesos; los buffers, pesos no cuantizados y KV cache requieren VRAM adicional. Los GPUs no comparten memoria contigua. No se admite el offload automático a CPU o disco para el servicio público.

| Candidato (selección explícita para modelos mayores) | Parámetros aprox. | Cuantización | Disco libre orientativo para descarga desde cero | Estado |
|---|---:|---|---:|---|
| Qwen3-32B | 32,8B densos | NF4 | 69 GiB | experimental, condicionado por disco/VRAM |
| Qwen3-30B-A3B | 30,5B total / 3,3B activos | NF4 | 65 GiB | experimental, no certificado |
| Qwen3-14B | 14,8B densos | NF4 | 33 GiB | primer candidato a comparar |
| Qwen3-8B | 8,2B densos | NF4 | 19 GiB | estable predeterminado |
| Qwen3-4B | 4B densos | NF4 | 11 GiB | alternativa |
| Qwen2.5-1.5B-Instruct | 1,54B densos | FP16 | 4 GiB | compatibilidad |

Todos los parámetros de un candidato denso participan en inferencia; las cifras no equivalen a inteligencia medida. Los mínimos de disco y memoria son estimaciones conservadoras, no resultados experimentales. Se acepta sólo un candidato que cargue sin offload CPU/disco y emita texto en una prueba breve. Esto **no** certifica calidad, velocidad aceptable ni estabilidad con contextos largos; ejecutar evaluaciones antes de declarar ganador. La API health informa el ID seleccionado sin exponer rutas. Caché de pesos durante la sesión, no garantizada entre sesiones.

### Alternativas investigadas

- [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B), [14B](https://huggingface.co/Qwen/Qwen3-14B), [8B](https://huggingface.co/Qwen/Qwen3-8B) y [4B](https://huggingface.co/Qwen/Qwen3-4B): Apache 2.0, modelos de texto multilingües y razonamiento publicado. Se elige una familia homogénea para compatibilidad de plantillas y carga. Los números publicados no son mediciones sobre T4.
- [Qwen2.5-3B](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct): licencia Qwen Research, no se selecciona automáticamente para un servicio público por sus condiciones. Qwen3-4B es una alternativa de licencia más permisiva.
- [Phi-4](https://huggingface.co/microsoft/phi-4): 14B, MIT, 16K; orientado principalmente a inglés, candidato de comparación.
- [DeepSeek-R1 Distill](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B): versiones densas 1.5/7/14/32B, MIT con atribución de modelos base. Especializado en razonamiento; el coste de secuencias largas requiere evaluación separada.
- [Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B): MoE, ~30B total, ~3B activos, Apache 2.0. Los pesos de todos los expertos deben caber; más pequeño activo no significa menor almacenamiento. Se puede intentar explícitamente con el evaluador, sin garantía de que todos los expertos sean cuantizables o quepan; no se activa de forma automática.
- [GPT-OSS-20B](https://huggingface.co/openai/gpt-oss-20b): MoE MXFP4; los requisitos de kernels y velocidad real en Turing deben verificarse. Una cifra de VRAM anunciada no demuestra compatibilidad T4.
- [Gemma 3](https://huggingface.co/google/gemma-3-27b-it): 12B/27B entre sus tamaños, términos Gemma y acceso condicionado según distribución. No requiere al visitante aceptar otras licencias en el perfil automático.
- Mistral Small 24B, Llama 8B y MiniMind original: candidatos alternativos, no comparados experimentalmente. Mistral y Llama tienen condiciones dependientes de versión; revisar fichas y licencias concretas antes de habilitar. MiniMind conserva su implementación original para investigación.
- [Qwen3.5/Qwen3.6](https://huggingface.co/docs/transformers/en/model_doc/qwen3_5): variantes densas 9B/27B con arquitectura híbrida multimodal y soporte de Transformers más reciente. No sustituyen al backend de texto sin validar compatibilidad (T4, kernels, plantilla, dependencias, cuantización) y calidad.

[NF4 y bitsandbytes](https://huggingface.co/docs/transformers/quantization/bitsandbytes) soportan Turing. GPTQ/AWQ/GGUF prequantizados son posibles alternativas para reducir descarga y espacio; requieren validar backend y calidad. Tensor parallelism y cache KV cuantizada no se activan sin medir sus costes. No se comparó la calidad entre modelos sin GPU.

## Inferencia y herramientas

Rápido: 3.072 tokens de contexto total / 512 de salida. Equilibrado: 6.144 / 1.536. Profundo: 8.192 / 3.072. Los saludos y solicitudes explícitas de un entero o sí/no tienen un presupuesto de hasta 64 tokens; si se solicita justificar, se conserva el presupuesto normal. Qwen3 usa el chat template oficial con `enable_thinking=False`; el modo profundo prioriza comprobaciones y explicaciones visibles en una sola generación, no expone trazas privadas ni afirma que se haya ejecutado una verificación externa. Para comparar con la modalidad anterior, activa `BOITIA_LEGACY_REVIEW=1` (dos pases acotados al presupuesto total). La calidad de ambos modos debe medirse.

Se conservan los turnos nuevos y la solicitud íntegra; se descartan turnos antiguos completos para ajustar el contexto. KV cache activo durante la generación, sin cache compartida entre usuarios. Si el contexto no cabe, se devuelve un error explícito. Se intenta mantener el modelo en una GPU si cabe con margen; para modelos mayores, se utiliza reparto Accelerate sin offload CPU/disco. El calentamiento se realiza durante la prueba inicial de generación. Se imprime el mapa de módulos, VRAM libre/total y memoria asignada por GPU. No se terminan procesos ajenos automáticamente.

**Transporte:** [Cloudflare Quick Tunnels no soporta SSE](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Para evitar una solicitud abierta durante toda la inferencia, la UI usa POST breve que devuelve identificador aleatorio y GET periódicos de texto acumulado. Los GET se reintentan tras fallos transitorios sin volver a ejecutar el POST; los errores terminales conservan contenido parcial. Las consultas completadas están temporalmente en RAM, con caducidad por inactividad de 120 segundos y límite de 16 registros, nunca en archivos o Git. No se reenvía automáticamente un POST ambiguo. Un cliente compatible aún puede usar SSE estándar, con heartbeat de 5 segundos; no se garantiza por Quick Tunnel. La API devuelve uso y métricas de generación, TTFT y primer fragmento visible. El método `/calcular 0.1+0.2` usa aritmética racional exacta y sólo permite las cuatro operaciones básicas y paréntesis. No hay herramientas externas o ejecución arbitraria.

## Memoria y recuperación

Las conversaciones, recuerdos y ejemplos permanecen en localStorage del navegador y origen. La selección de recuerdos es léxica (máximo cinco relevantes), no embeddings ni RAG semántico. Se conserva el identificador de almacenamiento existente y migración anterior. Edita/elimina recuerdos desde Memoria, y exporta/importa un respaldo JSON desde Configuración. Importar combina registros y no borra conversaciones existentes. Una URL nueva de Quick Tunnel tiene otro origen; **exporta antes de terminar la sesión** e importa en la nueva. No hay sincronización automática entre dispositivos o sesiones nuevas sin almacenamiento externo autenticado. Los ejemplos y recuerdos no alteran los pesos.

## SFT / QLoRA (operación privada, no endpoint web)

1. Exporta ejemplos voluntarios de Aprendizaje. Revisa el contenido y consentimiento; elimina datos privados e instrucciones inadecuadas.
2. Para cada par aprobado, calcula SHA256 de `json.dumps([pregunta.strip(), respuesta.strip()], ensure_ascii=False).encode()`. Guarda un hash por línea en un archivo privado `approved.txt`; revisa contenido completo antes de aprobarlo. La aprobación no se puede hacer desde la API pública.
3. En sesión Kaggle separada de inferencia, instala `requirements-boitia-train.txt`. Ejecuta, por ejemplo:

```bash
python -m boitia.train --dataset boitia-lessons.jsonl --approved approved.txt --output boitia-adapters/v1 --model Qwen/Qwen2.5-1.5B-Instruct
```

El curador rechaza duplicados, formatos inválidos, pares no aprobados y coincidencias con casos reservados. Esto no detecta todos los parafraseos maliciosos: revisión humana imprescindible. El script requiere al menos diez ejemplos distintos, separa una validación estable, enmascara los tokens del prompt y entrena LoRA NF4 con PEFT/Trainer en una GPU. El informe guarda loss antes/después sobre validación; el candidato nunca se activa automáticamente. Usa `--resume` para recuperar checkpoints si existen; preserva directorios versionados fuera del repositorio. La plantilla y límite de secuencia se validan sin truncar ejemplos. La suficiencia de datos o mejoras estadísticas no están garantizadas. DPO exige pares de preferencias curados, no se implementa todavía.

Para una versión candidata aprobada se requiere evaluar sobre el mismo modelo base y benchmarks reservados, revisar regresiones, privacidad, compatibilidad y seguridad. Evalúa y promociona explícitamente (requiere PEFT instalado y GPU):

```bash
python -m boitia.adapters evaluate --model Qwen/Qwen2.5-1.5B-Instruct --adapter boitia-adapters/v1/candidate --output adapter-evaluation.json
python -m boitia.adapters promote --report adapter-evaluation.json
```

La promoción compara casos reservados, exige mejora, cero regresiones y ausencia de errores/truncamientos nuevos. Es una condición mínima, no certificación de generalización. Revisa el informe antes de promover. El lanzador sólo recupera el adaptador para su mismo modelo base, desde `BOITIA_STATE/active.json` (por defecto `/kaggle/working/boitia-state`), con verificación del hash de pesos y configuración. La celda selecciona las dependencias de PEFT cuando existe un manifiesto aprobado en la ubicación por defecto. Si no existe, no coincide o no puede cargarse, se utiliza la base. Para rollback renombra el manifiesto `active.json` y reinicia el servidor, o restaura `previous.json` tras revisar su contenido. La carpeta privada y los pesos deben preservarse como salida privada del notebook; no se sincronizan con Git. No entrenar sobre conversaciones públicas indistintamente.

## Evaluación — comparación en Kaggle, no durante el servicio

Detén primero la celda de servicio (o usa una sesión GPU separada). Guarda los informes fuera de Git, reutiliza la misma caché y ejecuta cada comando como proceso independiente para liberar memoria al finalizar. No borres pesos ni estado. El evaluador exige el modelo indicado, sin fallback silencioso.

```bash
python -m unittest discover -s tests -v
node tests/ui_transport.test.cjs
python -m boitia.evaluation --model Qwen/Qwen3-8B --output /kaggle/working/8b.json
python -m boitia.evaluation --model Qwen/Qwen3-14B --output /kaggle/working/14b.json
python -m boitia.compare /kaggle/working/8b.json /kaggle/working/14b.json
# sólo si disco/VRAM disponibles:
python -m boitia.evaluation --model Qwen/Qwen3-30B-A3B --output /kaggle/working/30b.json
python -m boitia.evaluation --model Qwen/Qwen3-32B --output /kaggle/working/32b.json
# comparaciones de cuantización sobre el mismo 8B:
python -m boitia.evaluation --model Qwen/Qwen3-8B --quantization fp4 --output /kaggle/working/8b-fp4.json
python -m boitia.evaluation --model Qwen/Qwen3-8B --quantization int8 --output /kaggle/working/8b-int8.json
# comparación de modo profundo, ambas sobre el código actual:
BOITIA_LEGACY_REVIEW=1 python -m boitia.evaluation --model Qwen/Qwen3-8B --mode deep --output /kaggle/working/deep-review.json
python -m boitia.evaluation --model Qwen/Qwen3-8B --mode deep --output /kaggle/working/deep-single.json
```

El benchmark contiene 21 casos reservados: fábrica, variantes, aritmética, español, lógica, instrucciones, programación básica no ejecutada, contexto largo, justificación (rúbrica numérica mínima) y memoria de conversación. Registra wall time, TTFT en generación, primer texto visible, tokens/s, tokens, truncamiento, VRAM asignada/reservada pico por GPU, VRAM libre/total y pico RSS del proceso. Las medianas no equivalen a latencia móvil/túnel. La comparación requiere mejoras de casos, cero regresiones o errores nuevos y medianas de latencia no mayores a 1,5 veces el baseline (umbral configurable). La revisión humana y pruebas más amplias siguen siendo necesarias; no se activa automáticamente el ganador. Para comparar contra la versión exacta previa, usa un worktree local del commit `5e9ac52534e8a2e9359268c9c16c1d2176ee8897` y su evaluador de 19 casos; éste no medía TTFT, por lo que sólo se comparan métricas/casos comunes y no se usa el gate de 21 casos con informes de esquemas distintos.

Resultados locales de esta iteración: pruebas de Python y regresión JavaScript con API simulada. La prueba opcional `python tests/ui_regression.py` requiere Chromium funcional y Playwright; no se pudo ejecutar aquí por ausencia del binario efectivo. No hubo GPU, PyTorch ni Transformers instalados en desarrollo: ninguna métrica neuronal o superioridad de candidato fue verificada. Qwen3-8B permanece como baseline de servicio. Las pruebas de quantización FP4/INT8 son experimentales offline; el servidor mantiene NF4.

Regresión exacta: para fecha límite 8, orden DBEAC, coste 65, 12 válidas; para 4, BEDAC, coste 85, 2 válidas. La verificación enumera las permutaciones; el problema se mantiene fuera del curador de entrenamiento.

## Seguridad y rollback

Un único trabajo de GPU simultáneo; límites globales y por IP, validación JSON/contexto, mismo origen, no CORS, CSP, UI que inserta texto con DOM seguro, sin credenciales en frontend. No hay acceso por parte del modelo al sistema operativo ni ejecución de programas arbitrarios. La calculadora sólo interpreta un AST acotado sin llamadas ni nombres. El túnel público sigue siendo público: sin autenticación fuerte, no enviar información sensible. El aislamiento de recuerdos depende del navegador/origen; no protege frente a una persona con acceso al mismo perfil. No prometemos resistencia perfecta a prompt injection. No se persisten chats en el servidor; el transporte de polling mantiene únicamente respuestas efímeras en memoria. Si las sesiones libres no permiten uso compartido, operar localmente respetando las condiciones de Kaggle.

Para rollback, detén el proceso, usa una copia del commit anterior (por ejemplo `2a703825fd6ef6f63fe6cb88ff57372fb1f40210`) y su procedimiento de inicio original; no borres datos locales ni adaptadores. No se modificó la historia de Git ni el código MiniMind original. Si fallan los modelos nuevos, ejecuta con `BOITIA_MODEL=Qwen/Qwen3-8B` en el entorno del propietario.

## Límites conocidos

Sin acceso a una T4 en desarrollo no se certifica carga, latencia, velocidad, entrenamiento, túnel público ni UI móvil real. No se ha probado streaming neuronal con GPU; no hay Markdown completo/LaTeX, embeddings o RAG documental, persistencia remota privada automática, evaluación exhaustiva de modelos ni promoción automática. Mantener estos elementos explícitos y no convertir diagnósticos estimados en métricas reales.
