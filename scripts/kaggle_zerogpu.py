"""Run once in a separate CPU notebook with owner-selected Kaggle secrets."""
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    from kaggle_secrets import UserSecretsClient
    secrets=UserSecretsClient()
    try:
        hf=secrets.get_secret("HF_TOKEN")
        github=secrets.get_secret("BOITIA_GITHUB_TOKEN")
    except Exception:
        raise SystemExit("Habilitá HF_TOKEN y BOITIA_GITHUB_TOKEN únicamente en tu notebook privado.") from None
    if not hf or not github:raise SystemExit("Faltan secretos.")
    subprocess.run([sys.executable,"-m","pip","install","-q","huggingface-hub>=0.36,<2"],check=True)
    env=dict(os.environ,HF_TOKEN=hf,BOITIA_GITHUB_TOKEN=github)
    subprocess.run([sys.executable,"-u",str(ROOT/"scripts/deploy_zerogpu.py"),"--apply","--publish"],
                   cwd=ROOT,env=env,check=True)

if __name__=="__main__":main()
