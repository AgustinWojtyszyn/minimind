"""BoitIA public demo. Reuses a loaded Hugging Face causal language model."""
import asyncio
import collections
import ipaddress
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

MODEL_ID = "boitia"
BASE = "/api/boitia/v1"
FRONTEND_URL = "https://raw.githubusercontent.com/AgustinWojtyszyn/minimind/master/frontend/index.html"
MAX_BODY = 65536
MAX_INPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 512


def create_app(model, tokenizer, frontend_html):
    import torch
    app = FastAPI(title="BoitIA", docs_url=None, redoc_url=None, openapi_url=None)
    model.eval()
    gpu_lock = threading.Lock()
    limit_lock = threading.Lock()
    global_times = collections.deque()
    ip_times = {}

    def reject(status, detail):
        return JSONResponse({"error": {"message": detail}}, status_code=status,
                            headers={"Cache-Control": "no-store"})

    def rate_limit(request):
        # The server binds only to loopback; Cloudflare sets this header.
        ip = request.headers.get("cf-connecting-ip", "")
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError:
            ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with limit_lock:
            while global_times and now - global_times[0] >= 60:
                global_times.popleft()
            for key in list(ip_times):
                queue = ip_times[key]
                while queue and now - queue[0] >= 60:
                    queue.popleft()
                if not queue:
                    del ip_times[key]
            if len(global_times) >= 12 or len(ip_times.get(ip, ())) >= 4:
                return False
            global_times.append(now)
            ip_times.setdefault(ip, collections.deque()).append(now)
            return True

    @app.get("/", response_class=HTMLResponse)
    def home():
        return HTMLResponse(frontend_html, headers={"Cache-Control": "no-store",
                                                     "X-Content-Type-Options": "nosniff",
                                                     "Referrer-Policy": "no-referrer"})

    @app.get(BASE + "/models")
    def models():
        return {"object": "list", "data": [{"id": MODEL_ID, "object": "model",
                                             "owned_by": "boitia"}]}

    def generate(messages, max_tokens, temperature):
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        encoded = tokenizer(prompt, return_tensors="pt", return_token_type_ids=False,
                            add_special_tokens=False)
        if encoded["input_ids"].shape[-1] > MAX_INPUT_TOKENS:
            raise ValueError("La conversación supera el límite de contexto; iniciá una nueva.")
        device = next(model.parameters()).device
        encoded = {k: v.to(device) for k, v in encoded.items() if k in ("input_ids", "attention_mask")}
        kwargs = {"max_new_tokens": max_tokens, "do_sample": temperature > 0,
                  "pad_token_id": tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id}
        if temperature > 0:
            kwargs.update(temperature=temperature, top_p=0.9)
        with torch.inference_mode():
            output = model.generate(**encoded, **kwargs)
        answer = tokenizer.decode(output[0, encoded["input_ids"].shape[-1]:],
                                  skip_special_tokens=True).strip()
        if not answer:
            raise RuntimeError("El modelo devolvió una respuesta vacía.")
        return answer

    @app.post(BASE + "/chat/completions")
    async def complete(request: Request):
        # No CORS or cross-origin browser API access.
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        if origin and origin not in ("https://" + host, "http://" + host):
            return reject(403, "Origen no permitido.")
        if not request.headers.get("content-type", "").lower().startswith("application/json"):
            return reject(415, "Se requiere JSON.")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BODY:
                return reject(413, "Solicitud demasiado grande.")
            raw.extend(chunk)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or body.get("model") != MODEL_ID or body.get("stream"):
                raise ValueError()
            messages = body.get("messages")
            if not isinstance(messages, list) or not 1 <= len(messages) <= 21:
                raise ValueError()
            if any(not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant")
                   or not isinstance(m.get("content"), str) for m in messages):
                raise ValueError()
            if sum(len(m["content"]) for m in messages) > 24000 or messages[-1]["role"] != "user":
                raise ValueError()
            # Keep user-provided memories, but supply the server-side identity.
            clean = [{"role": "system", "content": "Eres BoitIA, una IA personal experimental. Responde con claridad. No inventes capacidades."}]
            for m in messages:
                if m["role"] == "system":
                    clean[0]["content"] += "\nContexto aportado por el usuario: " + m["content"]
                else:
                    clean.append({"role": m["role"], "content": m["content"]})
            max_tokens = max(1, min(MAX_OUTPUT_TOKENS, int(body.get("max_tokens", 256))))
            temperature = float(body.get("temperature", 0.6))
            if not 0 <= temperature <= 1.2:
                raise ValueError()
        except (ValueError, TypeError, OverflowError, UnicodeError):
            return reject(400, "Solicitud inválida o contexto demasiado largo.")
        if not gpu_lock.acquire(blocking=False):
            return reject(429, "BoitIA está atendiendo otra consulta. Reintentá en unos segundos.")
        if not rate_limit(request):
            gpu_lock.release()
            return reject(429, "Límite temporal de consultas. Reintentá en un minuto.")

        def work():
            try:
                return generate(clean, max_tokens, temperature)
            finally:
                gpu_lock.release()

        try:
            answer = await asyncio.shield(asyncio.get_running_loop().run_in_executor(None, work))
        except ValueError as e:
            return reject(400, str(e))
        except Exception:
            return reject(503, "El motor no pudo generar una respuesta.")
        return {"object": "chat.completion", "model": MODEL_ID,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                             "finish_reason": "stop"}]}

    return app


def launch(namespace):
    """Run once in Kaggle after loading the existing model. No retraining."""
    import uvicorn
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    source = "Qwen/Qwen2.5-1.5B-Instruct"
    if not torch.cuda.is_available():
        raise RuntimeError("Activá la GPU T4 en Kaggle y volvé a ejecutar esta celda.")
    candidates = []
    for key in ("engine", "candidate_model", "model", "loaded_model", "_boitia_model"):
        obj = namespace.get(key)
        if isinstance(obj, torch.nn.Module) and callable(getattr(obj, "generate", None)):
            candidates.append(obj)
    for obj in list(namespace.values()):
        if isinstance(obj, torch.nn.Module) and callable(getattr(obj, "generate", None)):
            if all(obj is not other for other in candidates):
                candidates.append(obj)
    model = next((obj for obj in candidates
                  if sum(p.numel() for p in obj.parameters()) == 1543714304
                  and getattr(obj.config, "model_type", "") == "qwen2"), None)
    if model is None:
        print("BoitIA: recuperando Qwen 1.5B desde la caché o Hugging Face...", flush=True)
        tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(
            source, torch_dtype=torch.float16, trust_remote_code=False
        ).to("cuda").eval()
    else:
        print("BoitIA: modelo existente encontrado.", flush=True)
        if next(model.parameters()).device.type != "cuda":
            model = model.to("cuda")
        model.eval()
        tokenizer = next((namespace.get(k) for k in ("candidate_tokenizer", "tok", "tokenizer", "engine_tokenizer", "_boitia_tokenizer")
                          if callable(getattr(namespace.get(k), "apply_chat_template", None))
                          and getattr(namespace.get(k), "name_or_path", "").rstrip("/").endswith("Qwen2.5-1.5B-Instruct")), None)
        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=False)
    namespace["_boitia_model"] = model
    namespace["_boitia_tokenizer"] = tokenizer
    print("BoitIA: motor listo en", next(model.parameters()).device, flush=True)
    print("BoitIA: descargando interfaz actualizada...", flush=True)
    with urllib.request.urlopen(FRONTEND_URL + "?v=" + str(time.time_ns()), timeout=30) as response:
        html = response.read().decode("utf-8")
    if "BoitIA" not in html or BASE not in html:
        raise RuntimeError("No se encontró la interfaz actualizada de BoitIA.")
    print("BoitIA: preparando Cloudflare...", flush=True)
    executable = shutil.which("cloudflared")
    if not executable:
        for root in (pathlib.Path("/kaggle/working"), pathlib.Path("/tmp")):
            if root.exists():
                executable = next((str(p) for p in root.glob("cloudflared*") if p.is_file() and os.access(p, os.X_OK)), None)
                if executable:
                    break
    if not executable:
        # Install the official binary into the notebook working directory.
        executable = str(pathlib.Path("/kaggle/working/cloudflared-boitia"))
        urllib.request.urlretrieve("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", executable)
        os.chmod(executable, 0o755)
    old = namespace.get("_boitia_runtime")
    if old:
        old[0].terminate()
        old[1].should_exit = True
        old[2].join(timeout=5)
        if old[2].is_alive():
            raise RuntimeError("El servidor anterior sigue ocupado.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(model, tokenizer, html),
                                           host="127.0.0.1", port=port, log_level="warning",
                                           access_log=False, proxy_headers=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.2)
    if not server.started:
        server.should_exit = True
        raise RuntimeError("No se pudo iniciar el servidor.")
    print("BoitIA: iniciando túnel público...", flush=True)
    process = subprocess.Popen([executable, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    namespace["_boitia_runtime"] = (process, server, thread)
    import queue
    lines = queue.Queue(maxsize=100)
    def drain():
        for line in process.stdout:
            try:
                lines.put_nowait(line)
            except queue.Full:
                pass
    threading.Thread(target=drain, daemon=True).start()
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and process.poll() is None:
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                continue
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)
                print("BoitIA — interfaz pública:", url, flush=True)
                print("Conexión automática; no se requiere token. Kaggle debe seguir activo.")
                return url
        raise RuntimeError("Cloudflare no entregó un enlace público.")
    except BaseException:
        process.terminate()
        server.should_exit = True
        raise
