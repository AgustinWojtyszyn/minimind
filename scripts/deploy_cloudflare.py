"""Deploy a shared Cloudflare worker only after the owner confirms the Free plan."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from boitia.remote_verify import verify_remote
from boitia.registry import publish_engine

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirmed-free-plan",action="store_true")
    args=parser.parse_args()
    if not args.apply:
        print("Dry run: no se crea ningún Worker.")
        return
    if not args.confirmed_free_plan:
        raise SystemExit("Confirmá que la cuenta usa Workers Free y no tiene Workers Paid.")
    subprocess.run([sys.executable,str(ROOT/"scripts/build_cloudflare.py")],cwd=ROOT,check=True)
    process=subprocess.Popen(["npx","--yes","wrangler@4","deploy","--config","deploy/cloudflare/wrangler.jsonc"],
                             cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    result=[]
    for line in process.stdout:
        print(line,end="",flush=True);result.append(line)
    if process.wait():raise SystemExit("No se desplegó el Worker.")
    urls=set(re.findall(r"https://boitia-ai\.[a-z0-9-]+\.workers\.dev","".join(result)))
    if len(urls)!=1:raise SystemExit("No se encontró una URL única. Copiá la URL workers.dev mostrada y verificala.")
    url=urls.pop()
    # One real test consumes a small amount of free allowance.
    verify_remote("cloudflare",url)
    print("Cloudflare verificado (consulta real y CORS): "+url,flush=True)
    token=os.environ.get("BOITIA_GITHUB_TOKEN")
    if token:
        publish_engine(url,token,provider="cloudflare")
        print("Registrado automáticamente en BoitIA.")
    else:
        print("Compartí solamente la URL workers.dev para registrar el respaldo en GitHub.")

if __name__=="__main__":main()
