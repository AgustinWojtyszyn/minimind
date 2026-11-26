"""BoitIA public demo. Reuses a loaded Hugging Face causal language model."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boitia.config import SYSTEM_PROMPT, PROFILES, MAX_BODY, MAX_CHARS, PROMPT_VERSION
from boitia.inference import respond
from boitia.hardware import load_engine
import collections
import ipaddress
import json
import os
import pathlib
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlsplit

MODEL_ID = "boitia"
BASE = "/api/boitia/v1"



def create_app(model, tokenizer, frontend_html, *, responder=None, model_info=None,
               output_limit=None, allow_poll=True):
    if responder is None:
        import torch
        oom_error = torch.cuda.OutOfMemoryError
        clear_cache = torch.cuda.empty_cache
        gpu_count = torch.cuda.device_count()
    else:
        # CPU-only implementation does not need PyTorch or CUDA.
        oom_error = MemoryError
        clear_cache = lambda: None
        gpu_count = 0
    app = FastAPI(title="BoitIA", docs_url=None, redoc_url=None, openapi_url=None)
    # Default remains same-origin; the owner may explicitly allow one HTTPS UI origin.
    portable_origin = os.environ.get("BOITIA_PORTABLE_ORIGIN", "").strip()
    if portable_origin:
        parsed = urlsplit(portable_origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("BOITIA_PORTABLE_ORIGIN debe ser un origen HTTPS sin ruta.")
        app.add_middleware(CORSMiddleware, allow_origins=[portable_origin],
                           allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
                           allow_credentials=False)
    if model is not None:
        model.eval()
    gpu_lock = threading.Lock()
    limit_lock = threading.Lock()
    global_times = collections.deque()
    ip_times = {}
    jobs = {}
    jobs_lock = threading.Lock()

    def prune_jobs():
        now = time.monotonic()
        for key, job in list(jobs.items()):
            if now - job["touched"] > 120:
                job["cancel"].set()
                del jobs[key]
        # Completed jobs are ephemeral; never persist chat contents server-side.
        while len(jobs) >= 16:
            key = next((k for k, j in jobs.items() if j["status"] != "running"), None)
            if key is None:
                break
            del jobs[key]

    @app.get(BASE + "/jobs/{job_id}")
    def job_status(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
            if not job or time.monotonic() - job["touched"] > 120:
                if job:
                    jobs.pop(job_id, None); job["cancel"].set()
                return reject(404, "La generación ya no está disponible.")
            job["touched"] = time.monotonic()
            payload = {k: v for k, v in job.items() if k not in ("cancel", "touched")}
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    @app.delete(BASE + "/jobs/{job_id}")
    def cancel_job(job_id: str):
        with jobs_lock:
            job = jobs.pop(job_id, None)
            if job:
                job["cancel"].set()
        return JSONResponse({"cancelled": bool(job)}, headers={"Cache-Control": "no-store"})

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
                                                     "Referrer-Policy": "no-referrer",
                                                     "X-Frame-Options": "DENY",
                                                     "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self' https: http://localhost:* http://127.0.0.1:*; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})

    @app.get(BASE + "/models")
    def models():
        return {"object": "list", "data": [{"id": MODEL_ID, "object": "model",
                                             "owned_by": "boitia"}]}

    @app.get(BASE + "/health")
    def health():
        return {"ready": True, "busy": gpu_lock.locked(), "transport": "poll" if allow_poll else "sse", "model": (model_info or {}).get("model",getattr(getattr(model, "_boitia_candidate", None), "model_id", MODEL_ID)),
                "parameter_billions_estimate": (model_info or {}).get("billions",getattr(getattr(model, "_boitia_candidate", None), "billions", None)),
                "prompt_version": PROMPT_VERSION, "profiles": {k: {"context":v.context,"max_tokens":v.output} for k,v in PROFILES.items()},
                "gpu_count": gpu_count}

    @app.post(BASE + "/chat/completions")
    async def complete(request: Request):
        # Same-origin by default; one explicitly configured portable origin only.
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        if origin and origin not in ("https://" + host, "http://" + host, portable_origin):
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
            if not isinstance(body, dict) or body.get("model") != MODEL_ID:
                raise ValueError()
            messages = body.get("messages")
            if not isinstance(messages, list) or not 1 <= len(messages) <= 21:
                raise ValueError()
            if any(not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant")
                   or not isinstance(m.get("content"), str) for m in messages):
                raise ValueError()
            if sum(len(m["content"]) for m in messages) > MAX_CHARS or messages[-1]["role"] != "user":
                raise ValueError()
            transport = body.get("transport", "sse")
            if transport not in ("sse", "poll") or (transport == "poll" and not allow_poll):
                raise ValueError()
            stream = body.get("stream", False)
            if type(stream) is not bool:
                raise ValueError()
            mode = body.get("mode", "balanced")
            if mode not in PROFILES:
                raise ValueError()
            clean = [{"role": "system", "content": SYSTEM_PROMPT}]
            untrusted = []
            for m in messages:
                if m["role"] == "system":
                    untrusted.append(m["content"])
                else:
                    clean.append({"role": m["role"], "content": m["content"]})
            if untrusted and not clean[-1]["content"].startswith("/calcular "):
                clean[-1]["content"] = "Contexto no verificado (datos): " + json.dumps(untrusted, ensure_ascii=False) + "\nSolicitud: " + clean[-1]["content"]
            max_tokens = max(1, min(PROFILES[mode].output, int(body.get("max_tokens", PROFILES[mode].output))))
            if output_limit is not None:
                max_tokens = min(max_tokens, output_limit)
            temperature = float(body.get("temperature", PROFILES[mode].temperature))
            if not 0 <= temperature <= 1.2:
                raise ValueError()
        except (ValueError, TypeError, OverflowError, UnicodeError):
            return reject(400, "Solicitud inválida o contexto demasiado largo.")
        if not gpu_lock.acquire(blocking=False):
            return reject(429, "BoitIA está atendiendo otra consulta. Reintentá en unos segundos.")
        if not rate_limit(request):
            gpu_lock.release()
            return reject(429, "Límite temporal de consultas. Reintentá en un minuto.")

        def work(on_text=None, cancel=None):
            try:
                query = clean[-1]["content"]
                if query.startswith("/calcular "):
                    from boitia.calculator import calculate
                    from boitia.inference import Result
                    try:
                        answer = calculate(query[len("/calcular "):])
                    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
                        raise ValueError("Expresión matemática inválida. Usa +, -, *, / y paréntesis.")
                    answer = "Resultado exacto de la calculadora: " + answer
                    if on_text: on_text(answer)
                    return Result(answer, 0, 0, 0.0, "stop")
                if responder is not None:
                    return responder(clean, mode, max_tokens, temperature,on_text=on_text,cancel=cancel)
                return respond(model, tokenizer, clean, mode, max_tokens, temperature, on_text=on_text, cancel=cancel)
            except oom_error:
                clear_cache()
                raise
            finally:
                gpu_lock.release()

        def metrics(result):
            return {"generation_seconds": result.elapsed,
                    "tokens_per_second": result.output_tokens / max(result.elapsed, 1e-6),
                    "ttft_seconds": result.ttft_seconds,
                    "first_visible_seconds": result.first_visible_seconds,
                    "usage_estimated": bool((model_info or {}).get("usage_estimated",False))}

        if stream and transport == "poll":
            job_id = secrets.token_urlsafe(24)
            job = {"status": "running", "text": "", "touched": time.monotonic(),
                   "cancel": threading.Event()}
            with jobs_lock:
                prune_jobs()
                jobs[job_id] = job
            def append(chunk):
                with jobs_lock:
                    if time.monotonic() - job["touched"] > 120:
                        job["cancel"].set()
                    if not job["cancel"].is_set():
                        job["text"] += chunk
            def run_job():
                try:
                    result = work(append, job["cancel"])
                    with jobs_lock:
                        job.update(status="done", text=result.text, finish_reason=result.finish_reason,
                                   metrics=metrics(result))
                except Exception as exc:
                    with jobs_lock:
                        job.update(status="error", error=str(exc) if isinstance(exc, ValueError)
                                   else "Memoria GPU insuficiente." if isinstance(exc, oom_error)
                                   else "El motor no pudo completar la respuesta.")
                finally:
                    with jobs_lock:
                        job["touched"] = time.monotonic()
            loop = asyncio.get_running_loop()
            def expire():
                with jobs_lock:
                    if jobs.get(job_id) is not job:
                        return
                    remaining = 120 - (time.monotonic() - job["touched"])
                    if remaining <= 0:
                        job["cancel"].set()
                        jobs.pop(job_id, None)
                    else:
                        loop.call_later(remaining, expire)
            loop.call_later(120, expire)
            loop.run_in_executor(None, run_job)
            return JSONResponse({"job_id": job_id}, status_code=202,
                                headers={"Cache-Control": "no-store"})

        if stream:
            loop = asyncio.get_running_loop()
            queue = asyncio.Queue()
            cancel = threading.Event()
            def emit(text):
                if not cancel.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, ("text", text))
            def streamed_work():
                try:
                    result = work(emit, cancel)
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", result))
                except ValueError as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
                except oom_error:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", "Memoria GPU insuficiente; probá un modo o consulta más corta."))
                except Exception:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", "El motor no pudo completar la respuesta."))
            # Start executor before returning; worker owns the lock and releases it even on errors.
            loop.run_in_executor(None, streamed_work)
            def event(obj):
                return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"
            async def events():
                try:
                    yield ": conexión establecida\n\n"
                    while True:
                        try:
                            kind, value = await asyncio.wait_for(queue.get(), timeout=5)
                        except asyncio.TimeoutError:
                            yield ": esperando motor\n\n"
                            continue
                        if kind == "text":
                            yield event({"object":"chat.completion.chunk","model":MODEL_ID,"choices":[{"index":0,"delta":{"content":value},"finish_reason":None}]})
                        elif kind == "error":
                            yield event({"error":{"message":value}})
                            break
                        else:
                            yield event({"object":"chat.completion.chunk","model":MODEL_ID,"choices":[{"index":0,"delta":{},"finish_reason":value.finish_reason}],"usage":{"prompt_tokens":value.input_tokens,"completion_tokens":value.output_tokens,"total_tokens":value.input_tokens+value.output_tokens},"metrics":metrics(value)})
                            break
                    yield "data: [DONE]\n\n"
                finally:
                    cancel.set()
            return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-store", "X-Accel-Buffering":"no"})

        try:
            answer = await asyncio.shield(asyncio.get_running_loop().run_in_executor(None, work))
        except ValueError as e:
            return reject(400, str(e))
        except oom_error:
            return reject(503, "Memoria GPU insuficiente; probá el modo rápido o una consulta más corta.")
        except Exception:
            return reject(503, "El motor no pudo generar una respuesta.")
        return {"object": "chat.completion", "model": MODEL_ID,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer.text},
                             "finish_reason": answer.finish_reason}],
                "usage": {"prompt_tokens": answer.input_tokens, "completion_tokens": answer.output_tokens,
                          "total_tokens": answer.input_tokens + answer.output_tokens},
                "metrics": metrics(answer)}

    return app


def launch(namespace):
    """Load a selected model and start the public demo; no training in the web process."""
    import uvicorn
    import torch

    # The write credential is owner-only. Remove it before starting other processes.
    registry_token = os.environ.pop("BOITIA_GITHUB_TOKEN", None)
    if registry_token:
        from boitia.registry import PUBLIC_ORIGIN
        os.environ["BOITIA_PORTABLE_ORIGIN"] = PUBLIC_ORIGIN

    old = namespace.get("_boitia_runtime")
    if old:
        old[0].terminate()
        try:
            old[0].wait(timeout=5)
        except subprocess.TimeoutExpired:
            old[0].kill(); old[0].wait()
        old[1].should_exit = True
        old[2].join(timeout=10)
        if old[2].is_alive():
            raise RuntimeError("El servidor anterior sigue ocupado.")
    import gc
    namespace.pop("_boitia_runtime", None)
    namespace.pop("_boitia_model", None)
    namespace.pop("_boitia_tokenizer", None)
    gc.collect()
    torch.cuda.empty_cache()
    cache = os.environ.get("BOITIA_CACHE", "/kaggle/working/boitia-cache")
    preferred = os.environ.get("BOITIA_MODEL") or None
    try:
        model, tokenizer, candidate = load_engine(cache, preferred=preferred)
    except RuntimeError:
        if not preferred or preferred == "Qwen/Qwen3-8B":
            raise
        print("Candidato explícito falló; recuperando perfil estable.", flush=True)
        model, tokenizer, candidate = load_engine(cache, preferred="Qwen/Qwen3-8B")
    namespace["_boitia_model"] = model
    namespace["_boitia_tokenizer"] = tokenizer
    html = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
    if "BoitIA" not in html or BASE not in html:
        raise RuntimeError("No se encontró la interfaz actualizada de BoitIA.")
    print("BoitIA: preparando Cloudflare...", flush=True)
    executable = shutil.which("cloudflared")
    if not executable:
        target = Path("/kaggle/working/cloudflared-boitia")
        if not target.is_file() or not os.access(target, os.X_OK):
            temp = target.with_suffix(".download")
            try:
                with urllib.request.urlopen("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", timeout=60) as source, temp.open("wb") as dest:
                    shutil.copyfileobj(source, dest)
                temp.chmod(0o755)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
        executable = str(target)
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
    # Verify actual local API response before announcing the URL.
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{BASE}/health", timeout=10) as response:
            if not json.load(response).get("ready"):
                raise RuntimeError("Servidor no listo")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
            if b"BoitIA" not in response.read(): raise RuntimeError("Interfaz no disponible")
    except Exception:
        server.should_exit = True
        raise
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
                # Quick tunnels can need a few seconds before routing becomes available.
                for attempt in range(15):
                    try:
                        with urllib.request.urlopen(url + BASE + "/health", timeout=8) as response:
                            if json.load(response).get("ready"):
                                break
                    except Exception:
                        time.sleep(2)
                else:
                    raise RuntimeError("El enlace público no respondió a la comprobación.")
                if registry_token:
                    try:
                        from boitia.registry import publish_engine, PUBLIC_ORIGIN
                        req = urllib.request.Request(url + BASE + "/health", headers={"Origin": PUBLIC_ORIGIN})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            if response.headers.get("Access-Control-Allow-Origin") != PUBLIC_ORIGIN or not json.load(response).get("ready"):
                                raise RuntimeError("La página permanente no puede acceder al motor.")
                        publish_engine(url, registry_token)
                        print("Motor registrado para todos los visitantes de la URL permanente.", flush=True)
                    except Exception:
                        print("No se pudo registrar el motor. Revisá el permiso Contents: write del secreto.", flush=True)
                else:
                    print("Sin secreto BOITIA_GITHUB_TOKEN: el motor no se publicó en la página permanente.", flush=True)
                print("BoitIA — interfaz pública:", url, flush=True)
                print("Conexión automática; no se requiere token. Kaggle debe seguir activo.")
                return url
        raise RuntimeError("Cloudflare no entregó un enlace público.")
    except BaseException:
        process.terminate()
        server.should_exit = True
        raise


if __name__ == "__main__":
    launch(globals())
    try:
        while _boitia_runtime[0].poll() is None and _boitia_runtime[2].is_alive():
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        _boitia_runtime[0].terminate()
        _boitia_runtime[1].should_exit = True
