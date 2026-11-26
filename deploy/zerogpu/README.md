---
title: BoitIA ZeroGPU
emoji: 🧠
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 5.49.1
python_version: 3.12
app_file: app.py
suggested_hardware: zero-a10g
models:
- Qwen/Qwen3-4B
license: apache-2.0
---

# BoitIA ZeroGPU experimental
Backend neuronal independiente con pesos abiertos Qwen3-4B. El proveedor aplica su cuota GPU y cola normal. No se contratan servicios, ni se modifica el modelo automáticamente. Sin almacenamiento de conversaciones en el servidor. La generación es limitada por solicitud.
