"""Owner-operated offline QLoRA SFT. Produces a candidate adapter, never activates it."""
import argparse
import os
import json
import hashlib
from pathlib import Path
from .learning import curate,split

def training_manifest(args, training, validation, world_size):
    def digest(rows):
        return hashlib.sha256(json.dumps([r['sha256'] for r in rows]).encode()).hexdigest()
    return {'schema':1,'model':args.model,'train_digest':digest(training),
            'validation_digest':digest(validation),'max_length':args.max_length,
            'epochs':args.epochs,'save_steps':args.save_steps,'world_size':world_size,
            'seed':args.seed,'quantization':'nf4','gradient_accumulation':8}


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def verify_run(output, manifest, resume):
    output = Path(output)
    path = output/'manifest.json'
    if resume:
        if not path.is_file() or json.loads(path.read_text()) != manifest:
            raise ValueError('La configuración o los datos no coinciden con el entrenamiento original.')
        if not any(p.is_dir() and all((p/f).is_file() for f in ('trainer_state.json','adapter_model.safetensors','optimizer.pt','scheduler.pt')) for p in output.glob('checkpoint-*')):
            raise ValueError('No hay checkpoint completo para reanudar.')
    else:
        if output.exists():
            raise ValueError('Utiliza un directorio nuevo o --resume.')
        output.mkdir(parents=True)
        atomic_json(path, manifest)


def train(args):
    if not 1 <= args.epochs <= 5 or not 1 <= args.save_steps <= 100 or not 128 <= args.max_length <= 2048:
        raise ValueError('Parámetros de entrenamiento fuera de los límites.')
    # One full quantized replica per rank, not model sharding. Two GPUs are opt-in via torchrun.
    world_size=int(os.environ.get('WORLD_SIZE','1'))
    rank=int(os.environ.get('RANK','0'))
    local_rank=int(os.environ.get('LOCAL_RANK','0'))
    if world_size not in (1,2):
        raise ValueError('Configuración soportada: una GPU o dos procesos DDP.')
    if world_size==1:
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments, EarlyStoppingCallback, set_seed
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from .config import SYSTEM_PROMPT
    if not torch.cuda.is_available() or torch.cuda.device_count() <= local_rank:
        raise RuntimeError('GPU requerida para cada proceso.')
    torch.cuda.set_device(local_rank)
    if world_size>1:
        torch.distributed.init_process_group(backend='nccl')
    set_seed(args.seed)
    output=Path(args.output)
    approved=set(Path(args.approved).read_text().splitlines())
    rows,rejected=curate(args.dataset,approved);training,validation=split(rows)
    manifest=training_manifest(args,training,validation,world_size)
    # Validate before downloading a model or spending GPU time.
    failure=[None]
    if rank==0:
        try: verify_run(output,manifest,args.resume)
        except (OSError,ValueError) as exc: failure[0]=str(exc)
    if world_size>1: torch.distributed.broadcast_object_list(failure,src=0)
    if failure[0]: raise ValueError(failure[0])
    tok=AutoTokenizer.from_pretrained(args.model,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(args.model,trust_remote_code=False,use_safetensors=True,
        torch_dtype=torch.float16,device_map={'':local_rank},quantization_config=BitsAndBytesConfig(load_in_4bit=True,
        bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16))
    model.config.use_cache=False
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.05,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
    def encode(row):
        prompt=[{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':row['question']}]
        kwargs={'enable_thinking':False} if getattr(model.config,'model_type','')=='qwen3' else {}
        prefix=tok.apply_chat_template(prompt,tokenize=True,add_generation_prompt=True,**kwargs)
        full=tok.apply_chat_template(prompt+[{'role':'assistant','content':row['answer']}],tokenize=True,**kwargs)
        if full[:len(prefix)]!=prefix or len(full)>args.max_length or len(full)<=len(prefix): raise ValueError('Ejemplo excede longitud o plantilla incompatible; revise dataset.')
        return {'input_ids':full,'attention_mask':[1]*len(full),'labels':[-100]*len(prefix)+full[len(prefix):]}
    train_data=[encode(r) for r in training];eval_data=[encode(r) for r in validation]
    def collate(batch):
        width=max(len(x['input_ids']) for x in batch);pad=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
        return {k:torch.tensor([x[k]+[(-100 if k=='labels' else 0 if k=='attention_mask' else pad)]*(width-len(x[k])) for x in batch]) for k in ('input_ids','attention_mask','labels')}
    trainer=Trainer(model=model,args=TrainingArguments(output_dir=str(output),per_device_train_batch_size=1,
        per_device_eval_batch_size=1,gradient_accumulation_steps=8,learning_rate=1e-4,num_train_epochs=args.epochs,
        fp16=True,save_steps=args.save_steps,save_total_limit=2,logging_steps=1,report_to=[],gradient_checkpointing=True,
        eval_strategy='steps',eval_steps=args.save_steps,save_strategy='steps',
        load_best_model_at_end=True,metric_for_best_model='eval_loss',greater_is_better=False,
        seed=args.seed,data_seed=args.seed,ddp_find_unused_parameters=False,
        remove_unused_columns=False),train_dataset=train_data,eval_dataset=eval_data,data_collator=collate,callbacks=[EarlyStoppingCallback(early_stopping_patience=2)] if args.epochs>1 else [])
    baseline=output/'baseline.json'
    if args.resume and baseline.is_file():
        before=json.loads(baseline.read_text())
    else:
        with model.disable_adapter(): before=trainer.evaluate()
        if rank==0: atomic_json(baseline,before)
    checkpoint=None
    if args.resume:
        complete=[p for p in output.glob('checkpoint-*') if all((p/f).is_file() for f in ('trainer_state.json','adapter_model.safetensors','optimizer.pt','scheduler.pt')) and p.name.split('-')[-1].isdigit()]
        if not complete: raise ValueError('No hay checkpoint completo.')
        checkpoint=str(max(complete,key=lambda p:int(p.name.split('-')[-1])))
    trainer.train(resume_from_checkpoint=checkpoint);after=trainer.evaluate()
    trainer.save_model(str(output/'candidate'))
    if rank==0:
        from .adapters import adapter_digest
        atomic_json(output/'report.json',{'base':args.model,'accepted':len(rows),'rejected':len(rejected),
            'train':len(training),'validation':len(validation),'before':before,'after':after,
            'manifest':manifest,'adapter_digest':adapter_digest(output/'candidate'),
            'status':'candidate_not_activated'})
    if world_size>1:
        torch.distributed.barrier()
        torch.distributed.destroy_process_group()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--approved',required=True);p.add_argument('--output',required=True);p.add_argument('--model',default='Qwen/Qwen2.5-1.5B-Instruct');p.add_argument('--max-length',type=int,default=768);p.add_argument('--resume',action='store_true');p.add_argument('--epochs',type=int,default=1);p.add_argument('--save-steps',type=int,default=10);p.add_argument('--seed',type=int,default=42);train(p.parse_args())
