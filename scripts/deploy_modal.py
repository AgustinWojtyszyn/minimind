"""Guard the documented Modal deployment flow; never deploy by default."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirmed-zero-budget",action="store_true")
    args=parser.parse_args()
    if not args.apply:
        print("Dry run: no Modal resource created.")
        return
    if not args.confirmed_zero_budget:
        raise SystemExit("No se permite desplegar sin comprobar previamente el límite neto de gasto USD 0 en Modal.")
    subprocess.run([sys.executable,"-m","modal","deploy",str(ROOT/"deploy/modal/app.py")],
                   cwd=ROOT,check=True)

if __name__=="__main__":main()
