"""Explicit owner-only deployment. Uses HF_TOKEN env; never accepts paid hardware."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--name",default="boitia-zerogpu")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--publish",action="store_true",help="Verify and register the public engine after build.")
    args=parser.parse_args()
    if not args.apply:
        print("Dry run: create/use personal ZeroGPU space; no paid hardware. Use --apply to deploy.")
        return
    if args.publish and not os.environ.get("BOITIA_GITHUB_TOKEN"):
        raise SystemExit("Falta BOITIA_GITHUB_TOKEN para publicar después de la comprobación.")
    token=os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Definí HF_TOKEN como secreto del entorno; no lo pegues en el repositorio.")
    from huggingface_hub import HfApi
    api=HfApi(token=token)
    owner=api.whoami()["name"]
    repo_id=f"{owner}/{args.name}"
    # Refuse to overwrite an existing Space, and never fall back to paid plans.
    try:
        api.create_repo(repo_id,repo_type="space",space_sdk="gradio",space_hardware="zero-a10g",
                        private=False,exist_ok=False)
    except Exception as exc:
        if getattr(getattr(exc,"response",None),"status_code",None)==402:
            raise SystemExit("Hugging Face no autorizó ZeroGPU gratuito para esta cuenta. No se adquirió ningún plan; revisá elegibilidad o grant.") from None
        raise
    runtime=api.get_space_runtime(repo_id)
    hardware=getattr(runtime,"hardware",None)
    requested=getattr(runtime,"requested_hardware",None)
    if "zero-a10g" not in (hardware, requested):
        raise SystemExit("El Space no tiene ZeroGPU confirmado. No se subió ni cambió el hardware.")
    if any(h and h!="zero-a10g" for h in (hardware,requested)):
        raise SystemExit("Hardware actual o solicitado distinto de ZeroGPU. Revisá el Space.")
    with tempfile.TemporaryDirectory() as tmp:
        target=Path(tmp)
        for name in ("README.md","app.py","requirements.txt"):
            shutil.copyfile(ROOT/"deploy/zerogpu"/name,target/name)
        (target/"boitia").mkdir()
        for name in ("__init__.py","config.py","inference.py"):
            shutil.copyfile(ROOT/"boitia"/name,target/"boitia"/name)
        api.upload_folder(folder_path=target,repo_id=repo_id,repo_type="space",
                          commit_message="BoitIA ZeroGPU experimental")
    print(f"https://huggingface.co/spaces/{repo_id}",flush=True)
    if args.publish:
        from boitia.registry import publish_engine,validate_provider_url
        from boitia.remote_verify import verify_remote
        deadline=time.monotonic()+1200
        while time.monotonic()<deadline:
            info=api.space_info(repo_id)
            runtime=api.get_space_runtime(repo_id)
            raw_stage=getattr(runtime,"stage","")
            stage=str(getattr(raw_stage,"value",raw_stage))
            if stage in ("BUILD_ERROR","RUNTIME_ERROR","CONFIG_ERROR","PAUSED","NO_APP_FILE"):
                raise SystemExit("El Space no completó el build: "+stage)
            if stage=="RUNNING" and getattr(info,"host",None):
                if getattr(runtime,"hardware",None)!="zero-a10g" or getattr(runtime,"requested_hardware",None) not in (None,"zero-a10g"):
                    raise SystemExit("ZeroGPU no confirmado; no se registró.")
                url=validate_provider_url("zerogpu",info.host.rstrip("/"))
                verify_remote("zerogpu",url)
                publish_engine(url,os.environ["BOITIA_GITHUB_TOKEN"],provider="zerogpu")
                print("ZeroGPU verificado y registrado para todos los visitantes.",flush=True)
                return
            print("Estado ZeroGPU:",stage,flush=True);time.sleep(15)
        raise SystemExit("El Space aún no está listo; no se registró.")

if __name__=="__main__":
    main()
