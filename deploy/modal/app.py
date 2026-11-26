"""Optional self-hosted Qwen on Modal. Deploy only after confirming zero net spend."""
import os
from pathlib import Path
import sys
import modal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
app = modal.App("boitia-ondemand")
cache = modal.Volume.from_name("boitia-model-cache", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("torch>=2.7,<3","transformers>=4.51,<5","accelerate>=1.6,<2",
                      "bitsandbytes>=0.46,<1","huggingface-hub>=0.30,<1","safetensors",
                      "fastapi>=0.115,<1","uvicorn>=0.34,<1")
         .add_local_python_source("boitia")
         .add_local_dir(str(ROOT/"frontend"),remote_path="/root/frontend"))

@app.cls(image=image,gpu="T4",cpu=2,memory=12288,volumes={"/cache":cache},
         min_containers=0,max_containers=1,buffer_containers=0,scaledown_window=10,timeout=240)
class Engine:
    @modal.enter()
    def load(self):
        from boitia.hardware import load_engine
        self.model,self.tokenizer,_=load_engine("/cache",preferred="Qwen/Qwen3-8B",load_approved=False)
        cache.commit()

    @modal.asgi_app()
    def serve(self):
        from frontend.boitia_server import create_app
        from boitia.registry import PUBLIC_ORIGIN
        os.environ["BOITIA_PORTABLE_ORIGIN"]=PUBLIC_ORIGIN
        # No queued background GPU jobs; request remains open until response.
        html=Path("/root/frontend/index.html").read_text()
        return create_app(self.model,self.tokenizer,html,output_limit=768,allow_poll=False)
