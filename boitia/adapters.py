"""Owner-only evaluation and promotion of local PEFT adapter candidates."""
import argparse
import hashlib
import json
from pathlib import Path


def adapter_digest(directory):
    directory=Path(directory)
    files=[directory/'adapter_config.json',directory/'adapter_model.safetensors']
    if any(not p.is_file() for p in files): raise ValueError('Adaptador incompleto; se requiere safetensors.')
    digest=hashlib.sha256()
    for p in files:
        digest.update(p.name.encode())
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def compare(base,candidate):
    """Require stricter-than-no-regression on every reserved case, not merely lower loss."""
    b={r['id']:r for r in base['results']}; c={r['id']:r for r in candidate['results']}
    if not b or set(b)!=set(c): return {'eligible':False,'reason':'different_cases'}
    regressions=[k for k in b if b[k]['passed'] and not c[k]['passed']]
    errors=[k for k in c if 'error' in c[k] or c[k].get('finish_reason')=='length' and b[k].get('finish_reason')!='length']
    improvements=[k for k in b if not b[k]['passed'] and c[k]['passed']]
    return {'eligible':bool(improvements) and not regressions and not errors,'improvements':improvements,'regressions':regressions,'errors':errors}


def evaluate(model_id, adapter, cache, output):
    from peft import PeftModel
    from .hardware import load_engine
    from .evaluation import run
    adapter=Path(adapter).resolve();digest=adapter_digest(adapter)
    model,tok,c=load_engine(cache,preferred=model_id,load_approved=False)
    base=run(model,tok)
    wrapped=PeftModel.from_pretrained(model,str(adapter),is_trainable=False).eval()
    candidate=run(wrapped,tok)
    result={'model':c.model_id,'adapter':str(adapter),'digest':digest,'base':base,'candidate':candidate,'decision':compare(base,candidate)}
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2));return result['decision']


def promote(report, state_dir):
    """Explicit local action after human review. Never called by API or training."""
    report=json.loads(Path(report).read_text()); decision=compare(report['base'],report['candidate'])
    if not decision['eligible']: raise ValueError('El candidato no superó el criterio de promoción.')
    directory=Path(state_dir);directory.mkdir(parents=True,exist_ok=True)
    adapter=Path(report['adapter']).resolve()
    if adapter_digest(adapter)!=report['digest']: raise ValueError('El adaptador cambió después de la evaluación.')
    data={'model':report['model'],'adapter':str(adapter),'digest':report['digest'],'decision':decision}
    path=directory/'active.json';temp=directory/'active.tmp'
    # Keep previous approved pointer for manual rollback.
    if path.exists(): (directory/'previous.json').write_text(path.read_text())
    temp.write_text(json.dumps(data,indent=2));temp.replace(path);return path


def rollback(state_dir):
    """Restore the previous verified adapter; no implicit model changes."""
    directory=Path(state_dir)
    previous=directory/'previous.json'
    active=directory/'active.json'
    if not previous.is_file():
        raise ValueError('No hay un adaptador anterior.')
    data=json.loads(previous.read_text())
    if data['decision'].get('eligible') is not True or adapter_digest(data['adapter'])!=data['digest']:
        raise ValueError('El adaptador anterior no está verificado.')
    old=active.read_text() if active.exists() else None
    temp=directory/'active.tmp'
    temp.write_text(json.dumps(data,indent=2))
    temp.replace(active)
    if old is not None:
        previous.write_text(old)
    else:
        previous.unlink()
    return active


def approved_for(model_id,state_dir):
    path=Path(state_dir)/'active.json'
    if not path.exists(): return None
    data=json.loads(path.read_text())
    if data['model']!=model_id: return None
    if data['decision'].get('eligible') is not True or adapter_digest(data['adapter'])!=data['digest']:
        raise ValueError('Manifiesto de adaptador inválido.')
    return data['adapter']


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    e=sub.add_parser('evaluate');e.add_argument('--model',required=True);e.add_argument('--adapter',required=True);e.add_argument('--output',required=True);e.add_argument('--cache',default='/kaggle/working/boitia-cache')
    p=sub.add_parser('promote');p.add_argument('--report',required=True);p.add_argument('--state',default='/kaggle/working/boitia-state')
    r=sub.add_parser('rollback');r.add_argument('--state',default='/kaggle/working/boitia-state')
    a=parser.parse_args()
    if a.action=='evaluate': print(evaluate(a.model,a.adapter,a.cache,a.output))
    elif a.action=='promote': print(promote(a.report,a.state))
    else: print(rollback(a.state))
