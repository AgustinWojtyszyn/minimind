"""Owner-operated offline QLoRA SFT. Produces a candidate adapter, never activates it."""
import argparse
import os
import json
from pathlib import Path
from .learning import curate,split

def train(args):
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from .config import SYSTEM_PROMPT
    if not torch.cuda.is_available(): raise RuntimeError('GPU requerida')
    output=Path(args.output)
    if output.exists() and not args.resume: raise ValueError('Utiliza un directorio nuevo o --resume.')
    approved=set(Path(args.approved).read_text().splitlines())
    rows,rejected=curate(args.dataset,approved);training,validation=split(rows)
    tok=AutoTokenizer.from_pretrained(args.model,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(args.model,trust_remote_code=False,use_safetensors=True,
        torch_dtype=torch.float16,device_map={'':0},quantization_config=BitsAndBytesConfig(load_in_4bit=True,
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
        per_device_eval_batch_size=1,gradient_accumulation_steps=8,learning_rate=1e-4,num_train_epochs=1,
        fp16=True,save_steps=10,save_total_limit=2,logging_steps=1,report_to=[],gradient_checkpointing=True,
        remove_unused_columns=False),train_dataset=train_data,eval_dataset=eval_data,data_collator=collate)
    with model.disable_adapter(): before=trainer.evaluate()
    trainer.train(resume_from_checkpoint=args.resume or None);after=trainer.evaluate()
    trainer.save_model(str(output/'candidate'))
    (output/'report.json').write_text(json.dumps({'base':args.model,'accepted':len(rows),'rejected':len(rejected),
       'train':len(training),'validation':len(validation),'before':before,'after':after,'status':'candidate_not_activated'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--approved',required=True);p.add_argument('--output',required=True);p.add_argument('--model',default='Qwen/Qwen2.5-1.5B-Instruct');p.add_argument('--max-length',type=int,default=768);p.add_argument('--resume',action='store_true');train(p.parse_args())
