"""Update only the code version of the existing Worker; leave domains/triggers intact."""
import os
import json
from urllib.error import HTTPError
import re
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from boitia.remote_verify import verify_remote

def main():
    if "--confirmed-free-plan" not in sys.argv or not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise SystemExit("Confirmá Workers Free y cargá el token de despliegue.")
    subprocess.run([sys.executable,str(ROOT/"scripts/build_cloudflare.py")],cwd=ROOT,check=True)
    cmd=["npx","--yes","wrangler@4","versions"]
    config=["--config","deploy/cloudflare/wrangler.jsonc"]
    upload=subprocess.run(cmd+["upload"]+config,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(upload.stdout,flush=True)
    if upload.returncode:raise SystemExit("No se pudo subir la versión.")
    match=re.search(r"(?:Worker Version ID|Version ID):\s*([0-9a-f-]{36})",upload.stdout,re.I)
    if not match:raise SystemExit("No se identificó la versión; revisá el resultado.")
    subprocess.run(cmd+["deploy",match.group(1)+"@100%","-y"]+config,cwd=ROOT,check=True)
    print("Versión actualizada; dominios sin cambios.",flush=True)
    try:
        print("Cloudflare verificado:",verify_remote("cloudflare","https://boitia-ai.agustinwojtyszyn.com"),flush=True)
    except HTTPError as exc:
        print("Prueba HTTP:",exc.code,flush=True)
        try:
            info=json.loads(exc.read(4096)).get("error",{})
            print("Diagnóstico:",info.get("stage"),info.get("provider_code"),flush=True)
        except (ValueError,AttributeError):
            pass
        raise SystemExit(1) from None
    except Exception as exc:
        print("La prueba aún no pasó:",type(exc).__name__,flush=True)
        raise SystemExit(1) from None

if __name__=="__main__":main()
