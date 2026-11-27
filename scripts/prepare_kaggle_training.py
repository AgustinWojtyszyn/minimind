"""Prepare a private, GPU-bounded Kaggle notebook for an already approved dataset.

No upload, provider authentication, quota use or training occurs in this script.
The owner must separately verify the dataset's private visibility and GPU quota.
"""
import argparse
import json
import re
from pathlib import Path

MODEL_IDS = ('Qwen/Qwen2.5-1.5B-Instruct', 'Qwen/Qwen3-4B', 'Qwen/Qwen3-8B')
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{1,79}/[a-z0-9][a-z0-9-]{1,79}$')


def prepare(output, kernel, dataset, revision, model, epochs, gpu_count):
    if not SLUG.fullmatch(kernel) or not SLUG.fullmatch(dataset):
        raise ValueError('Identificador Kaggle inválido.')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Se requiere un commit Git exacto.')
    if model not in MODEL_IDS or not 1 <= epochs <= 3 or gpu_count not in (1, 2):
        raise ValueError('Configuración de entrenamiento inválida.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        'id': kernel, 'title': 'Boiti private QLoRA training',
        'code_file': 'train.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': True, 'enable_internet': True,
        'dataset_sources': [dataset], 'competition_sources': [],
        'kernel_sources': [],
    }
    repo = '/kaggle/working/boiti-source'
    source = '/kaggle/input/' + dataset.split('/')[1]
    target = '/kaggle/working/boiti-training'
    script = f'''import subprocess, sys, pathlib, torch
root = pathlib.Path({repo!r})
source = pathlib.Path({source!r})
if not source.is_dir():
    raise RuntimeError("Dataset privado no montado.")
dataset = source / "training.jsonl"
approved = source / "approved.sha256"
if not dataset.is_file() or not approved.is_file():
    raise RuntimeError("Faltan datos aprobados por el propietario.")
if torch.cuda.device_count() < {gpu_count}:
    raise RuntimeError("No hay suficientes GPU para esta configuración.")
subprocess.run(["git", "clone", "https://github.com/AgustinWojtyszyn/minimind.git", str(root)], check=True)
subprocess.run(["git", "-C", str(root), "checkout", "--detach", {revision!r}], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(root/"requirements-boitia-train.txt")], check=True)
launcher = [sys.executable, "-m", "torch.distributed.run", "--standalone", "--nproc_per_node=2", "-m"] if {gpu_count} == 2 else [sys.executable, "-m"]
subprocess.run(launcher+["boitia.train", "--dataset", str(dataset), "--approved", str(approved),
    "--output", {target!r}, "--model", {model!r}, "--epochs", str({epochs}), "--save-steps", "10"], cwd=root, check=True)
'''
    (output/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2))
    (output/'train.py').write_text(script)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--kernel',required=True)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--model',choices=MODEL_IDS,default=MODEL_IDS[0])
    parser.add_argument('--epochs',type=int,default=1)
    parser.add_argument('--gpu-count',type=int,default=1)
    a=parser.parse_args()
    prepare(a.output,a.kernel,a.dataset,a.revision,a.model,a.epochs,a.gpu_count)
