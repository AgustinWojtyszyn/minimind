"""Owner-side smoke test before exposing any shared remote engine."""
import json
import re
import time
import urllib.request
from .registry import PUBLIC_ORIGIN, NoRedirect, validate_provider_url

def verify_remote(provider,url,*,opener=None):
    root=validate_provider_url(provider,url)
    opener=opener or urllib.request.build_opener(NoRedirect())
    def request(method,path,body=None,extra=None):
        payload=None if body is None else json.dumps(body).encode()
        headers={"Origin":PUBLIC_ORIGIN}
        if body is not None:headers["Content-Type"]="application/json"
        if extra:headers.update(extra)
        response=opener.open(urllib.request.Request(root+path,data=payload,method=method,headers=headers),timeout=240)
        if response.headers.get("Access-Control-Allow-Origin") not in (PUBLIC_ORIGIN,"*"):
            response.close()
            raise RuntimeError("El motor no permite el origen de BoitIA Pages.")
        return response
    path="/gradio_api/call/complete" if provider=="zerogpu" else "/api/boitia/v1/chat/completions"
    with request("OPTIONS",path,extra={"Access-Control-Request-Method":"POST",
                                      "Access-Control-Request-Headers":"content-type"}):
        pass
    messages=[{"role":"user","content":"¿Cuánto es 2+2? Respondé únicamente el número."}]
    if provider=="zerogpu":
        with request("POST",path,{"data":[{"messages":messages,"mode":"fast"}]}) as response:
            event=json.load(response).get("event_id")
        if not isinstance(event,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}",event):
            raise RuntimeError("Identificador de generación inválido.")
        with request("GET",path+"/"+event) as response:
            kind=None
            answer=None
            deadline=time.monotonic()+180
            for line in response:
                if time.monotonic()>deadline:raise RuntimeError("ZeroGPU agotó el tiempo de prueba.")
                decoded=line.decode().strip()
                if decoded.startswith("event:"):kind=decoded[6:].strip()
                if kind=="error":raise RuntimeError("ZeroGPU no completó la prueba.")
                if kind=="complete" and decoded.startswith("data:"):
                    answer=json.loads(decoded[5:].strip())[0]["text"]
                    break
    else:
        with request("GET","/api/boitia/v1/health") as response:
            if not json.load(response).get("ready"):raise RuntimeError("Motor no listo.")
        with request("POST",path,{"model":"boitia","messages":messages,"mode":"fast",
                                  "max_tokens":32,"temperature":0,"stream":False}) as response:
            answer=json.load(response)["choices"][0]["message"]["content"]
    if not isinstance(answer,str) or answer.strip().strip(".")!="4":
        raise RuntimeError("El motor no aprobó la prueba de cálculo simple.")
    return answer
