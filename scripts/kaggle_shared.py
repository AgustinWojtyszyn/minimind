"""Owner bootstrap, run in Kaggle after retrieving the latest master."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    from kaggle_secrets import UserSecretsClient
    try:
        token = UserSecretsClient().get_secret("BOITIA_GITHUB_TOKEN")
    except Exception:
        raise SystemExit("Creá y habilitá el secreto BOITIA_GITHUB_TOKEN en Add-ons / Secrets de Kaggle.") from None
    if not token:
        raise SystemExit("El secreto BOITIA_GITHUB_TOKEN está vacío.")
    state = Path("/kaggle/working/boitia-state")
    requirements = "requirements-boitia-train.txt" if (state/"active.json").is_file() else "requirements-boitia.txt"
    print("BoitIA: instalando dependencias...", flush=True)
    subprocess.run([sys.executable,"-m","pip","install","-r",str(ROOT/requirements)],check=True)
    subprocess.run(["nvidia-smi"],check=True)
    env = dict(os.environ, BOITIA_GITHUB_TOKEN=token, BOITIA_MODEL="Qwen/Qwen3-8B", BOITIA_LEGACY_REVIEW="0")
    # Only the engine process receives the write secret; it removes it before launching Cloudflare.
    print("BoitIA: iniciando motor compartido...",flush=True)
    subprocess.run([sys.executable,"-u",str(ROOT/"frontend/boitia_server.py")],cwd=ROOT,env=env,check=True)


if __name__ == "__main__":
    main()
