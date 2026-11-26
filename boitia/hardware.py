"""Conservative hardware selection; measured load plus smoke test is mandatory."""
import gc
import shutil
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Candidate:
    model_id: str
    billions: float
    bits: int
    disk_gib: int
    min_budget_gib: int

# Disk estimates refer to downloading original FP16/BF16 weights, not VRAM.
CANDIDATES = (
    Candidate('Qwen/Qwen3-32B', 32.8, 4, 69, 21),
    Candidate('Qwen/Qwen3-14B', 14.8, 4, 33, 12),
    Candidate('Qwen/Qwen3-8B', 8.2, 4, 19, 7),
    Candidate('Qwen/Qwen3-4B', 4.0, 4, 11, 4),
    Candidate('Qwen/Qwen2.5-1.5B-Instruct', 1.54, 16, 4, 4),
)

def select_candidates(budgets, disk_gib, candidates=CANDIDATES):
    return [c for c in candidates if disk_gib >= c.disk_gib and sum(budgets) >= c.min_budget_gib]

def load_engine(cache_dir, *, preferred=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from huggingface_hub import snapshot_download
    if not torch.cuda.is_available():
        raise RuntimeError('Activá una GPU en Kaggle.')
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    # Per-device headroom for CUDA context, KV cache and temporary allocations.
    budgets = [max(0, int(torch.cuda.mem_get_info(i)[0] / 2**30) - 3) for i in range(torch.cuda.device_count())]
    print('BoitIA: presupuesto de pesos por GPU (GiB):', budgets, flush=True)
    disk = shutil.disk_usage(cache).free / 2**30
    candidates = list(CANDIDATES)
    if preferred:
        candidates = [c for c in candidates if c.model_id == preferred]
    errors = []
    for c in candidates:
        if sum(budgets) < c.min_budget_gib:
            continue
        model = tokenizer = None
        try:
            try:
                source = snapshot_download(c.model_id, cache_dir=str(cache), local_files_only=True)
                # A tokenizer-only / partially cached snapshot is not proof that weights exist.
                if not list(Path(source).glob('*.safetensors')):
                    raise FileNotFoundError('Sin pesos en caché')
            except Exception:
                if disk < c.disk_gib:
                    continue
                source = c.model_id
            print('BoitIA: probando', c.model_id, f'{c.bits} bits', flush=True)
            kwargs = dict(cache_dir=str(cache), trust_remote_code=False, torch_dtype=torch.float16,
                          device_map='auto', max_memory={i: f'{v}GiB' for i,v in enumerate(budgets) if v > 0},
                          attn_implementation='sdpa', low_cpu_mem_usage=True, use_safetensors=True)
            if c.bits == 4:
                kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
                    bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
            tokenizer = AutoTokenizer.from_pretrained(source, cache_dir=str(cache), trust_remote_code=False)
            model = AutoModelForCausalLM.from_pretrained(source, **kwargs).eval()
            mapping = getattr(model, 'hf_device_map', {})
            if any(str(v) in ('cpu','disk') for v in mapping.values()):
                raise RuntimeError('Descarga CPU/disco no admitida en perfil público')
            from boitia.inference import generate
            result = generate(model, tokenizer, [{'role':'system','content':'Responde brevemente.'},
                {'role':'user','content':'¿Cuánto es dos más dos?'}], 'fast', 32)
            if not result.text.strip():
                raise RuntimeError('Prueba neuronal vacía')
            print('Motor seleccionado:', c.model_id, '· salida de prueba:', repr(result.text), flush=True)
            model._boitia_candidate = c
            return model, tokenizer, c
        except Exception as exc:
            errors.append(f'{c.model_id}: {type(exc).__name__}')
            print('Candidato descartado:', errors[-1], flush=True)
            model = tokenizer = None
            gc.collect(); torch.cuda.empty_cache()
            disk = shutil.disk_usage(cache).free / 2**30
    raise RuntimeError('Ningún candidato superó la carga y prueba: ' + ', '.join(errors))
