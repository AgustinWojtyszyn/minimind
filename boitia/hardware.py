"""Conservative hardware selection; measured load plus smoke test is mandatory."""
import gc
import os
import shutil
from dataclasses import dataclass, replace
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
    Candidate('Qwen/Qwen3-30B-A3B', 30.5, 4, 65, 21),
    Candidate('Qwen/Qwen3-14B', 14.8, 4, 33, 12),
    Candidate('Qwen/Qwen3-8B', 8.2, 4, 19, 7),
    Candidate('Qwen/Qwen3-4B', 4.0, 4, 11, 4),
    Candidate('Qwen/Qwen2.5-1.5B-Instruct', 1.54, 16, 4, 4),
)

def select_candidates(budgets, disk_gib, candidates=CANDIDATES):
    return [c for c in candidates if disk_gib >= c.disk_gib and sum(budgets) >= c.min_budget_gib]

def load_engine(cache_dir, *, preferred=None, load_approved=True, quantization="nf4"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from huggingface_hub import snapshot_download
    if quantization not in ('nf4', 'fp4', 'int8'):
        raise ValueError('Cuantización desconocida')
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
    else:
        # Keep the established 8B service until a larger candidate passes real tests.
        stable = ('Qwen/Qwen3-8B', 'Qwen/Qwen3-4B', 'Qwen/Qwen2.5-1.5B-Instruct')
        candidates = [next(c for c in CANDIDATES if c.model_id == name) for name in stable]
    errors = []
    for c in candidates:
        if quantization == 'int8' and c.bits == 4:
            c = replace(c, bits=8, min_budget_gib=max(c.min_budget_gib, int(c.billions*1.15)+2))
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
                          device_map='sequential' if max(budgets) >= c.min_budget_gib else 'auto',
                          max_memory={i: f'{v}GiB' for i,v in enumerate(budgets) if v > 0},
                          attn_implementation='sdpa', low_cpu_mem_usage=True, use_safetensors=True)
            if c.bits == 4:
                kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,
                    bnb_4bit_quant_type=quantization, bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
            elif c.bits == 8:
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            tokenizer = AutoTokenizer.from_pretrained(source, cache_dir=str(cache), trust_remote_code=False)
            model = AutoModelForCausalLM.from_pretrained(source, **kwargs).eval()
            mapping = getattr(model, 'hf_device_map', {})
            if any(str(v) in ('cpu','disk') for v in mapping.values()):
                raise RuntimeError('Descarga CPU/disco no admitida en perfil público')
            if load_approved:
                from boitia.adapters import approved_for
                try:
                    approved = approved_for(c.model_id, os.environ.get('BOITIA_STATE','/kaggle/working/boitia-state'))
                except (ValueError, OSError, KeyError):
                    print('Manifiesto de adaptador inválido; se usará el modelo base.', flush=True)
                    approved = None
                if approved:
                    try:
                        from peft import PeftModel
                        model=PeftModel.from_pretrained(model, approved, is_trainable=False).eval()
                        print('Adaptador previamente aprobado recuperado.', flush=True)
                    except Exception as exc:
                        # Reload pristine base rather than reuse possibly mutated modules.
                        print('No se pudo recuperar el adaptador; restaurando base:',type(exc).__name__,flush=True)
                        model=None
                    if model is None:
                        gc.collect();torch.cuda.empty_cache()
                        model=AutoModelForCausalLM.from_pretrained(source, **kwargs).eval()
            from boitia.inference import generate
            result = generate(model, tokenizer, [{'role':'system','content':'Responde brevemente.'},
                {'role':'user','content':'¿Cuánto es dos más dos?'}], 'fast', 32)
            if not result.text.strip():
                raise RuntimeError('Prueba neuronal vacía')
            if not mapping:
                print('Mapa de dispositivos no disponible.', flush=True)
            else:
                counts = {}
                for device in mapping.values():
                    counts[str(device)] = counts.get(str(device), 0) + 1
                print('Distribución de módulos por dispositivo:', counts, flush=True)
            print('VRAM libre/total (GiB):', [tuple(round(x/2**30,2) for x in torch.cuda.mem_get_info(i))
                for i in range(torch.cuda.device_count())], flush=True)
            print('Motor seleccionado:' , c.model_id, '· salida de prueba:', repr(result.text), flush=True)
            print('Prueba breve:', result.output_tokens, 'tokens en', round(result.elapsed,2), 's; VRAM asignada (GiB)', [round(torch.cuda.memory_allocated(i)/2**30,2) for i in range(torch.cuda.device_count())], flush=True)
            model._boitia_candidate = c
            model._boitia_quantization = quantization if c.bits != 16 else "fp16"
            return model, tokenizer, c
        except Exception as exc:
            errors.append(f'{c.model_id}: {type(exc).__name__}')
            print('Candidato descartado:', errors[-1], flush=True)
            model = tokenizer = None
            gc.collect(); torch.cuda.empty_cache()
            disk = shutil.disk_usage(cache).free / 2**30
    raise RuntimeError('Ningún candidato superó la carga y prueba: ' + ', '.join(errors))
