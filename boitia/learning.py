"""Offline dataset curation. Browser exports are NOT approved training data."""
import hashlib
import json
import re
from pathlib import Path

def normalize(text): return ' '.join(text.casefold().split())

def fingerprint(question): return hashlib.sha256(normalize(question).encode()).hexdigest()

def curate(path, approved_ids):
    # The owner manually reviews each question/answer before listing its hash.
    from .evaluation import cases
    heldout={fingerprint(c['prompt']) for c in cases()}
    seen=set(); accepted=[]; rejected=[]
    with Path(path).open(encoding='utf-8') as f:
        for i,line in enumerate(f,1):
            try:
                if len(line)>40000: raise ValueError('long')
                row=json.loads(line); msgs=row['conversations']
                if len(msgs)!=2 or [m['role'] for m in msgs]!=['user','assistant']: raise ValueError('roles')
                q,a=[m['content'].strip() for m in msgs]
                if not 4<=len(q)<=8000 or not 4<=len(a)<=16000: raise ValueError('length')
                key=fingerprint(q); pair=hashlib.sha256(json.dumps([q,a],ensure_ascii=False).encode()).hexdigest()
                if key in seen or key in heldout or ('fábrica' in normalize(q) and 'prioridad' in normalize(q)):
                    raise ValueError('duplicate_or_heldout')
                if pair not in approved_ids: raise ValueError('not_approved')
                seen.add(key);accepted.append({'question':q,'answer':a,'sha256':pair})
            except (ValueError,TypeError,KeyError,AttributeError,IndexError): rejected.append(i)
    return accepted,rejected

def split(rows):
    if len(rows)<10: raise ValueError('Se requieren al menos 10 ejemplos aprobados y distintos.')
    ordered=sorted(rows,key=lambda x:fingerprint(x['question']));n=max(2,len(rows)//5)
    return ordered[n:],ordered[:n]
