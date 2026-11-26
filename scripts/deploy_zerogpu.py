"""Explicit owner-only deployment. Uses HF_TOKEN env; never accepts paid hardware."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--name",default="boitia-zerogpu")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if not args.apply:
        print("Dry run: create/use personal ZeroGPU space; no paid hardware. Use --apply to deploy.")
        return
    token=os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Definí HF_TOKEN como secreto del entorno; no lo pegues en el repositorio.")
    from huggingface_hub import HfApi
    api=HfApi(token=token)
    owner=api.whoami()["name"]
    repo_id=f"{owner}/{args.name}"
    # Refuse to overwrite an existing Space, and never fall back to paid plans.
    api.create_repo(repo_id,repo_type="space",space_sdk="gradio",space_hardware="zero-a10g",
                    private=False,exist_ok=False)
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
    print(f"https://huggingface.co/spaces/{repo_id}")

if __name__=="__main__":
    main()
