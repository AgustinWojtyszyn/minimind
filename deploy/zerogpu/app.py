"""Standalone Gradio ZeroGPU prototype. Only use on actual ZeroGPU hardware."""
import gradio as gr
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from boitia.config import SYSTEM_PROMPT, PROFILES
from boitia.inference import respond

MODEL = "Qwen/Qwen3-4B"
# ZeroGPU virtualizes CUDA at startup; the decorator leases a real GPU per call.
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=False)
model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16,
                                            low_cpu_mem_usage=True, trust_remote_code=False).eval().to("cuda")

@spaces.GPU(duration=45)
def complete(body):
    if not isinstance(body, dict):
        raise gr.Error("Solicitud inválida.")
    messages = body.get("messages")
    mode = body.get("mode", "balanced")
    if not isinstance(mode,str) or mode not in PROFILES or not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise gr.Error("Solicitud inválida.")
    if any(not isinstance(m, dict) or m.get("role") not in ("user", "assistant") or
           not isinstance(m.get("content"), str) for m in messages):
        raise gr.Error("Mensajes inválidos.")
    if messages[-1]["role"] != "user" or sum(len(m["content"]) for m in messages) > 12000:
        raise gr.Error("Contexto demasiado largo.")
    clean = [{"role":"system", "content":SYSTEM_PROMPT}] + [{"role":m["role"], "content":m["content"]} for m in messages]
    result = respond(model, tokenizer, clean, mode, max_tokens=min(512, PROFILES[mode].output))
    return {"text":result.text,"model":MODEL,"finish_reason":result.finish_reason,
            "generation_seconds":result.elapsed}

with gr.Blocks(title="BoitIA ZeroGPU", analytics_enabled=False) as demo:
    gr.Markdown("# BoitIA · motor ZeroGPU experimental\nModelo Qwen3-4B alojado con GPU bajo demanda. Cuota y cola gestionadas por Hugging Face.")
    body=gr.JSON(value={"messages":[{"role":"user","content":"Hola"}],"mode":"balanced"},label="Solicitud")
    response=gr.JSON(label="Respuesta")
    gr.Button("Consultar").click(complete,body,response,api_name="complete",concurrency_limit=1)
demo.queue(default_concurrency_limit=1, max_size=8).launch()
