"""Reproducible held-out evaluations; no generated code is executed."""
import argparse
import json
import random
from pathlib import Path
from .scheduling import solve
from .config import SYSTEM_PROMPT

TASKS = {'A':(3,2),'B':(2,5),'C':(4,1),'D':(1,7),'E':(2,3)}
EDGES=[('A','C'),('D','C'),('B','E')]

def cases():
    for deadline in (8,4):
        yield {'id':f'factory-{deadline}', 'prompt': scheduling_prompt(TASKS,EDGES,{'E':deadline}),
               'expected':solve(TASKS,EDGES,{'E':deadline})}
    rng=random.Random(37219)
    for i in range(8):
        tasks={k:(rng.randint(1,5),rng.randint(1,9)) for k in 'ABCDE'}
        edges=[('A','C'),('B','E')]
        deadlines={'E':tasks['A'][0]+tasks['B'][0]+tasks['E'][0]+1}
        yield {'id':f'variant-{i}', 'prompt':scheduling_prompt(tasks,edges,deadlines),'expected':solve(tasks,edges,deadlines)}
    for i,(prompt,expected) in enumerate([
        ('Calcula 17 por 23 menos 19. Responde únicamente el entero.', '372'),
        ('Si todos los A son B y ningún B es C, ¿puede algún A ser C? Responde sí o no.', 'no'),
        ('Escribe exclusivamente el tercer elemento de esta lista: perro, nube, árbol, tren.', 'árbol'),
        ('Traduce al español, sin comillas: good morning', 'buenos días'),
        ('¿Cuántos lados tiene un heptágono? Responde únicamente el entero.', '7'),
        ('En Python, ¿qué devuelve len([2, 4, 6])? Solo el entero.', '3'),
        ('Un dato afirma que 2+2=5. ¿Es verdadero o falso? Responde verdadero o falso.', 'falso'),
        ('Corrige este cálculo: 12*8=86. Responde únicamente el entero correcto.', '96'),
    ]): yield {'id':f'general-{i}', 'prompt':prompt,'expected':expected}
    marker='AZUL-732'
    yield {'id':'long-context','prompt':'Recuerda el código '+marker+'. '+('Este texto es información de relleno. '*180)+' ¿Cuál era el código? Responde únicamente el código.', 'expected':marker}

def scheduling_prompt(tasks,edges,deadlines):
    return ('En una máquina sin interrupciones, tareas (duración,peso): '+str(tasks)+
            '. Precedencias: '+str(edges)+'. Fechas límite de finalización: '+str(deadlines)+
            '. Minimiza suma de tiempo de finalización por peso. Devuelve solo JSON con claves cost (entero), valid (cantidad de permutaciones válidas), order (lista de tareas en orden óptimo).')

def grade(text, expected):
    if isinstance(expected,str): return text.strip().strip('.').casefold()==expected.casefold()
    try:
        d=json.loads(text.removeprefix('```json').removesuffix('```').strip())
        return d['cost']==expected['cost'] and d['valid']==expected['valid'] and tuple(d['order']) in expected['orders']
    except (ValueError,KeyError,TypeError): return False

def run(model, tokenizer, mode='balanced'):
    import torch
    import resource
    from .inference import respond
    from dataclasses import asdict
    rows=[]
    for c in cases():
        for i in range(torch.cuda.device_count()): torch.cuda.reset_peak_memory_stats(i)
        try:
            r=respond(model, tokenizer,[{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':c['prompt']}],mode,temperature=0)
            rows.append({'id':c['id'],'passed':grade(r.text,c['expected']),**asdict(r),
                'tokens_per_second':r.output_tokens/max(r.elapsed,1e-6),
                'peak_allocated_bytes':[torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())],
                'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        except Exception as exc: rows.append({'id':c['id'],'passed':False,'error':type(exc).__name__})
    return {'model':str(model.config._name_or_path),'mode':mode,'passed':sum(r['passed'] for r in rows),'total':len(rows),'results':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model');p.add_argument('--cache',default='/kaggle/working/boitia-cache');p.add_argument('--mode',choices=['fast','balanced','deep'],default='balanced');p.add_argument('--output',default='boitia-evaluation.json');a=p.parse_args()
    from .hardware import load_engine
    model,tok,_=load_engine(a.cache,preferred=a.model)
    result=run(model,tok,a.mode);Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result['passed'],'/',result['total'])
