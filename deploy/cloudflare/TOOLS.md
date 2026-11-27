# BoitIA — herramientas del asistente

Las herramientas se ejecutan en la página pública de GitHub Pages. No necesitan nuevos secretos, Workers, cuentas ni suscripciones. No modifica el modelo neuronal ni su cuota de inferencia; las peticiones de investigación pueden aumentar los tokens de entrada. No hay llamadas de herramientas en mensajes ordinarios.

## Cómo usar

- "Creá un PDF sobre el sistema solar": botón PDF debajo de la respuesta.
- "Prepará un documento Word con una carta": botón Word.
- "Armá una planilla Excel con una tabla de gastos": botón Excel. Los números simples se almacenan como números y las fórmulas como texto, sin ejecutarlas.
- "Creá un gráfico de estos datos: enero 120, febrero 150": botón Gráfico (SVG descargable, desde tabla de dos columnas).
- "Investigá la historia de San Juan con fuentes verificables": se consultan resúmenes reales de Wikipedia en español (inglés si no hay resultados). Las fuentes se muestran separadas con enlaces reales.
- "Investigá estudios científicos sobre [tema]": también consulta metadatos de Crossref cuando estén disponibles. No lee automáticamente el texto íntegro de investigaciones.
- "Leé https://es.wikipedia.org/wiki/San_Juan_(Argentina)": lee el resumen introductorio mediante la API.
- Adjuntar archivo: TXT, Markdown, JSON, CSV, TSV, DOCX, XLSX o PDF de texto. El texto extraído se envía al motor al enviar la consulta; se conserva solo el nombre del archivo en el historial, no el archivo original.

## Límites y privacidad

- Investigación restringida a Wikipedia y Crossref, no navegación web general, noticias en tiempo real, comercio, sitios con login, ni enlaces externos arbitrarios. Las búsquedas envían el tema a las APIs públicas; no incluyen el banco de memoria ni el historial automáticamente. Los datos externos se etiquetan como no confiables.
- Adjuntos: un archivo de hasta 8 MB, hasta 6.500 caracteres extraídos; PDF hasta 12 páginas, solo texto (sin OCR). XLSX lee sheet1.xml y valores almacenados, no fórmulas ni otras hojas. Office puede requerir DecompressionStream del navegador. El PDF lector carga PDF.js 4.10.38 desde jsDelivr únicamente al solicitar lectura PDF. Si el servicio o navegador no permite extracción, se informa el error.
- Exportaciones locales sin nuevas llamadas de IA: PDF básico de texto con caracteres WinAnsi (español soportado; emojis y otros caracteres no representables se sustituyen por '?'), DOCX básico y XLSX con una hoja y hasta 500 filas/50 columnas, SVG hasta 30 barras. No son editores ofimáticos completos.
- La selección es por intención textual y el archivo se crea con el contenido de la respuesta terminada, no con un supuesto archivo inventado por el modelo. Si no hay una tabla de valores válida no se crea gráfico.
- Las imágenes y el OCR de PDFs escaneados todavía no están implementados. La visión nativa de Gemma requiere validar el transporte multimodal y desplegar un Worker nuevo.
- Para no introducir regresiones, el servidor directo de Kaggle mantiene su interfaz original, sin estas herramientas. La página pública puede usarlas con los motores existentes.

## Pruebas

\`node tests/ui_tools.test.cjs\` verifica formatos, escapes, estructura, fuentes simuladas, selección automática y adjuntos. Validar además el flujo real desde la página publicada, especialmente CORS, importación PDF.js y apertura de los archivos en aplicaciones de escritorio.

### Descarga de respuestas ya terminadas

El botón PDF/Word/Excel aparece al finalizar una consulta que solicita el formato, incluso con frases como «dame un PDF», «haceme un recetario en PDF» o «pasame eso a PDF». Para una respuesta normal, se puede abrir «Descargar respuesta como archivo». No se hace una consulta adicional al motor. Si el modelo incluye una introducción errónea del tipo «no puedo generar un archivo» seguida de contenido, se descarta solo esa introducción de capacidad, no las restricciones legítimas ni el contenido.

### Archivos v3
Las solicitudes de documento muestran el botón de descarga antes y después del contenido. Se eliminan del texto presentado y del archivo las introducciones genéricas incorrectas sobre exportación cuando hay contenido real, incluso en históricos, sin modificar el historial almacenado. El PDF A4 distingue títulos y cuerpo, usa encabezado y pie con número de página. El pie del chat indica «archivos v3» cuando se ha cargado esta versión de las herramientas.

### Archivos v4 — entrega exclusiva del PDF
Cuando una consulta solicita solamente un PDF, el chat muestra «Preparando tu PDF…» durante la generación y luego una confirmación breve y el botón de descarga. El contenido completo se almacena una sola vez en el mensaje para reconstruir el archivo sin consumir más inferencia; se materializa localmente en memoria. Las fuentes, si existen, quedan dentro del documento. Se admite la descarga parcial identificada como tal. Las consultas normales y las solicitudes explícitas que incluyen tanto PDF como texto en el chat conservan la vista habitual.

En las siguientes consultas, los PDF anteriores se representan en el historial enviado al modelo con una nota breve y su título, salvo cuando el usuario hace una referencia explícita al documento anterior o solicita modificarlo. Esto reduce tokens de entrada; el costo de generar el contenido original del PDF sigue existiendo. No se borra el historial ni el contenido de los archivos.
