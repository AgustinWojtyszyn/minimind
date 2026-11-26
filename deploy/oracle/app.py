"""CPU server for an owner-controlled Always Free VM. No third-party inference API."""
import os
from pathlib import Path
import uvicorn
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from boitia.cpu_inference import CPUResponder
from boitia.registry import PUBLIC_ORIGIN
from frontend.boitia_server import create_app

ROOT=Path(__file__).resolve().parents[2]
MODEL="Qwen/Qwen2.5-1.5B-Instruct-GGUF"
filename="qwen2.5-1.5b-instruct-q4_k_m.gguf"
model_path=hf_hub_download(MODEL,filename=filename,cache_dir="/cache")
llm=Llama(model_path=model_path,n_ctx=4096,n_threads=2,n_gpu_layers=0,chat_format="chatml",verbose=False)
os.environ["BOITIA_PORTABLE_ORIGIN"]=PUBLIC_ORIGIN
app=create_app(None,None,(ROOT/"frontend/index.html").read_text(),responder=CPUResponder(llm),
               model_info={"model":"Qwen2.5-1.5B · CPU","billions":1.54,"usage_estimated":True},output_limit=256)
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=8080,access_log=False,proxy_headers=False)
