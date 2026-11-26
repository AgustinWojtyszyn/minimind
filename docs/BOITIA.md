# BoitIA — arquitectura y operación

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
state=Path('/kaggle/working/boitia-state')
requirements='requirements-boitia-train.txt' if (state/'active.json').is_file() else 'requirements-boitia.txt'
subprocess.run([sys.executable,'-m','pip','install','-q','-r',str(repo/requirements)],check=True)
subprocess.run([sys.executable,'-u',str(repo/'frontend/boitia_server.py')],cwd=repo,check=True)
```

La celda queda ejecutándose para mantener el proceso vivo. El servidor verifica una generación neuronal real antes de abrir el túnel; comprueba `/health` local y público. Sólo entonces anuncia la URL. Para detenerlo, interrumpe la celda. La URL es temporal y la sesión está sujeta a límites y reglas de Kaggle y Cloudflare Quick Tunnels. No hay garantía de servicio continuo. No se piden tokens a visitantes. El modelo se descarga de Hugging Face con Internet habilitado; no se reinstala PyTorch. Para forzar un candidato de la lista, el propietario puede definir `BOITIA_MODEL` en el entorno; `BOITIA_CACHE` permite indicar un cache disponible. El lanzador no borra otros modelos ni datos.

## Motor y candidatos

Arquitectura: navegador → FastAPI de mismo origen → validación y límite de concurrencia → motor PyTorch/Transformers → pesos cuantizados distribuidos por Accelerate. Reserva nominal de 3 GiB por GPU, FP16 para Turing y SDPA (no FlashAttention 2 obligatoria ni BF16). La cuantización NF4 doble reduce memoria de pesos; los buffers, pesos no cuantizados y KV cache requieren VRAM adicional. Los GPUs no comparten memoria contigua. No se admite el offload automático a CPU o disco para el servicio público.

| Candidato (orden de intento) | Parámetros aprox. | Cuantización | Disco libre orientativo para descarga desde cero | Estado |
|---|---:|---|---:|---|
| Qwen3-32B | 32,8B densos | NF4 | 69 GiB | experimental, condicionado por disco/VRAM |
| Qwen3-14B | 14,8B densos | NF4 | 33 GiB | candidato preferido razonable |
| Qwen3-8B | 8,2B densos | NF4 | 19 GiB | alternativa |
| Qwen3-4B | 4B densos | NF4 | 11 GiB | alternativa |
| Qwen2.5-1.5B-Instruct | 1,54B densos | FP16 | 4 GiB | compatibilidad |

Todos los parámetros de un candidato denso participan en inferencia; las cifras no equivalen a inteligencia medida. Los mínimos de disco y memoria son estimaciones conservadoras, no resultados experimentales. Se acepta sólo un candidato que cargue sin offload CPU/disco y emita texto en una prueba breve. Esto **no** certifica calidad, velocidad aceptable ni estabilidad con contextos largos; ejecutar evaluaciones antes de declarar ganador. La API health informa el ID seleccionado sin exponer rutas. Caché de pesos durante la sesión, no garantizada entre sesiones.

### Alternativas investigadas

- [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B), [14B](https://huggingface.co/Qwen/Qwen3-14B), [8B](https://huggingface.co/Qwen/Qwen3-8B) y [4B](https://huggingface.co/Qwen/Qwen3-4B): Apache 2.0, modelos de texto multilingües y razonamiento publicado. Se elige una familia homogénea para compatibilidad de plantillas y carga. Los números publicados no son mediciones sobre T4.
- [Qwen2.5-3B](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct): licencia Qwen Research, no se selecciona automáticamente para un servicio público por sus condiciones. Qwen3-4B es una alternativa de licencia más permisiva.
- [Phi-4](https://huggingface.co/microsoft/phi-4): 14B, MIT, 16K; orientado principalmente a inglés, candidato de comparación.
- [DeepSeek-R1 Distill](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B): versiones densas 1.5/7/14/32B, MIT con atribución de modelos base. Especializado en razonamiento; el coste de secuencias largas requiere evaluación separada.
- [Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B): MoE, ~30B total, ~3B activos, Apache 2.0. Los pesos de todos los expertos deben caber; más pequeño activo no significa menor almacenamiento. No se activa hasta probar kernels y cuantización.
- [GPT-OSS-20B](https://huggingface.co/openai/gpt-oss-20b): MoE MXFP4; los requisitos de kernels y velocidad real en Turing deben verificarse. Una cifra de VRAM anunciada no demuestra compatibilidad T4.
- [Gemma 3](https://huggingface.co/google/gemma-3-27b-it): 12B/27B entre sus tamaños, términos Gemma y acceso condicionado según distribución. No requiere al visitante aceptar otras licencias en el perfil automático.
- Mistral Small 24B, Llama 8B y MiniMind original: candidatos alternativos, no comparados experimentalmente. Mistral y Llama tienen condiciones dependientes de versión; revisar fichas y licencias concretas antes de habilitar. MiniMind conserva su implementación original para investigación.
- [Qwen3.5/Qwen3.6](https://huggingface.co/docs/transformers/en/model_doc/qwen3_5): variantes densas 9B/27B con arquitectura híbrida multimodal y soporte de Transformers más reciente. No sustituyen al backend de texto sin validar compatibilidad (T4, kernels, plantilla, dependencias, cuantización) y calidad.

[NF4 y bitsandbytes](https://huggingface.co/docs/transformers/quantization/bitsandbytes) soportan Turing. GPTQ/AWQ/GGUF prequantizados son posibles alternativas para reducir descarga y espacio; requieren validar backend y calidad. Tensor parallelism y cache KV cuantizada no se activan sin medir sus costes. No se comparó la calidad entre modelos sin GPU.

## Inferencia y herramientas

Rápido: 3.072 tokens de contexto total / 512 de salida. Equilibrado: 6.144 / 1.536. Profundo: 8.192 / 3.072, borrador interno limitado a 768 y revisión independiente mediante otra generación del mismo motor cuando el presupuesto permite; no es garantía de corrección. No se publica el borrador. Los turnos antiguos se descartan íntegramente si el contexto no cabe; la última consulta no se recorta silenciosamente. API devuelve `finish_reason`, uso real de tokens y duración de generación en modo no streaming. El frontend público consume SSE con fragmentos de texto del `TextStreamer` durante la generación y el modo profundo transmite sólo la respuesta final. Las métricas de modo profundo incluyen el borrador cuando se usa. Sin ejecución arbitraria ni herramientas externas; `/calcular 0.1+0.2` usa aritmética racional exacta y sólo permite las cuatro operaciones básicas y paréntesis. El solver de planificación de hasta 8 tareas es un verificador offline, no una respuesta pregrabada.

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

## Evaluación

```bash
python -m unittest discover -s tests -v
python -m boitia.evaluation --model Qwen/Qwen2.5-1.5B-Instruct --output baseline.json
python -m boitia.evaluation --model Qwen/Qwen3-14B --output optimized.json
```

El benchmark local contiene 19 casos reservados: dos regresiones de fábrica, ocho variantes deterministas, aritmética, español, lógica, instrucciones, comprensión, programación básica, corrección de falsedades y contexto. Verificación exacta del JSON de planificación y coincidencia normalizada para respuestas cortas. No ejecuta código generado. Registra tiempos, tokens, truncamiento, picos de VRAM por GPU y RSS máximo del proceso. No sustituye GSM8K/MATH/HumanEval/MBPP/MMLU-Pro/ARC/IFEval ni mide TTFT: integrar suites externas y calibrar calidad antes de publicar comparativas. En entorno de desarrollo se ejecutaron unitarias CPU y prueba de API con modelo simulado; no hubo GPU, torch ni Transformers. No se midieron tokens/s neuronales.

Regresión exacta: para fecha límite 8, orden DBEAC, coste 65, 12 válidas; para 4, BEDAC, coste 85, 2 válidas. La verificación enumera las permutaciones; el problema se mantiene fuera del curador de entrenamiento.

## Seguridad y rollback

Un único trabajo de GPU simultáneo; límites globales y por IP, validación JSON/contexto, mismo origen, no CORS, CSP, UI que inserta texto con DOM seguro, sin credenciales en frontend. No hay acceso por parte del modelo al sistema operativo ni ejecución de programas arbitrarios. La calculadora sólo interpreta un AST acotado sin llamadas ni nombres. El túnel público sigue siendo público: sin autenticación fuerte, no enviar información sensible. El aislamiento de recuerdos depende del navegador/origen; no protege frente a una persona con acceso al mismo perfil. No prometemos resistencia perfecta a prompt injection. No se guardan chats en el servidor. Si las sesiones libres no permiten uso compartido, operar localmente respetando las condiciones de Kaggle.

Para rollback, detén el proceso, usa una copia del commit anterior (por ejemplo `2a703825fd6ef6f63fe6cb88ff57372fb1f40210`) y su procedimiento de inicio original; no borres datos locales ni adaptadores. No se modificó la historia de Git ni el código MiniMind original. Si fallan los modelos nuevos, ejecuta con `BOITIA_MODEL=Qwen/Qwen2.5-1.5B-Instruct` en el entorno del propietario.

## Límites conocidos

Sin acceso a una T4 en desarrollo no se certifica carga, latencia, velocidad, entrenamiento, túnel público ni UI móvil real. No se ha probado streaming neuronal con GPU; no hay Markdown completo/LaTeX, embeddings o RAG documental, persistencia remota privada automática, evaluación exhaustiva de modelos ni promoción automática. Mantener estos elementos explícitos y no convertir diagnósticos estimados en métricas reales.
