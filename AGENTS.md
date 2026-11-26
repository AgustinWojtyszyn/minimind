# BoitIA — reglas permanentes

- Mantener el frontend y la API pública de mismo origen; probar antes de cambiar rutas o formatos.
- No utilizar APIs comerciales como reemplazo de los pesos locales. No inventar resultados ni confundir memoria con entrenamiento.
- No incluir secretos, conversaciones, datasets personales, checkpoints ni respaldos en Git.
- Mantener el motor público sin acceso a shell, Python arbitrario, ficheros privados, herramientas externas ni entrenamiento remoto.
- Usar ejemplos voluntarios, revisados por el propietario; separar pruebas de datos de entrenamiento. Nunca activar automáticamente un adaptador.
- Preferir mediciones reproducibles y cambios pequeños. No anunciar rendimiento en T4 sin mediciones en T4.
- Conservar LICENSE, README y código MiniMind original y sus atribuciones. El nombre visible de la aplicación es BoitIA.
- Ejecutar `python -m unittest discover -s tests -v`, `python -m compileall -q boitia frontend` y comprobación JavaScript antes de actualizar master.
