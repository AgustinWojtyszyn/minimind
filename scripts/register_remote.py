"""Explicit owner registration after a real smoke test. No provider secrets in Git."""
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from boitia.registry import publish_engine, validate_provider_url
from boitia.remote_verify import verify_remote

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--provider",choices=["modal","zerogpu","cpu","cloudflare"],required=True)
    parser.add_argument("--url",required=True)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirmed-zero-budget",action="store_true",
                        help="Only after confirming provider cost protection manually")
    opts=parser.parse_args()
    validate_provider_url(opts.provider,opts.url)
    if not opts.apply:
        print("Dry run: no service queried and no change to registry.")
        return
    if opts.provider in ("modal","cloudflare") and not opts.confirmed_zero_budget:
        raise SystemExit("Confirmá primero el plan Free de Cloudflare o el límite neto USD 0 de Modal.")
    token=os.environ.get("BOITIA_GITHUB_TOKEN")
    if not token:raise SystemExit("Falta BOITIA_GITHUB_TOKEN en el entorno privado.")
    verify_remote(opts.provider,opts.url)
    publish_engine(opts.url,token,provider=opts.provider)
    print("Motor validado y registrado para todos los visitantes.")

if __name__=="__main__":main()
