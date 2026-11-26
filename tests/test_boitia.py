import json
import tempfile
import unittest
from pathlib import Path
from boitia.config import PROFILES
from boitia.hardware import select_candidates
from boitia.scheduling import solve
from boitia.evaluation import TASKS, EDGES, cases, grade
from boitia.learning import curate, split
from boitia.memory import select_memories
from boitia.calculator import calculate
import hashlib

class Tests(unittest.TestCase):
    def test_factory(self):
        for d,c,n,o in [(8,65,12,tuple('DBEAC')),(4,85,2,tuple('BEDAC'))]:
            r=solve(TASKS,EDGES,{'E':d});self.assertEqual((r['cost'],r['valid'],r['orders']), (c,n,[o]))
    def test_infeasible(self): self.assertEqual(solve(TASKS,EDGES,{'E':0})['valid'],0)
    def test_bound(self):
        with self.assertRaises(ValueError): solve({str(i):(1,1) for i in range(9)},[],{})
    def test_cases(self):
        items=list(cases());self.assertEqual(len(items),19);self.assertEqual(len(set(c['id'] for c in items)),19)
        for c in items[:10]:
            e=c['expected'];self.assertTrue(grade(json.dumps({'cost':e['cost'],'valid':e['valid'],'order':e['orders'][0]}),e))
    def test_models(self):
        self.assertEqual(select_candidates([10,10],40)[0].model_id,'Qwen/Qwen3-14B')
        self.assertEqual(select_candidates([3,3],5)[0].model_id,'Qwen/Qwen2.5-1.5B-Instruct')
        self.assertFalse(select_candidates([0],100))
    def test_profiles(self): self.assertLess(PROFILES['fast'].output,PROFILES['balanced'].output);self.assertLess(PROFILES['balanced'].output,PROFILES['deep'].output)
    def test_memory(self): self.assertEqual(select_memories('mi perro Kiara',['perro Kiara marrón','compré pan']),['perro Kiara marrón'])
    def test_calculator(self):
        self.assertEqual(calculate("(0.1+0.2)/3"),"1/10")
        with self.assertRaises(ValueError):calculate("abs(5)")
        with self.assertRaises(ValueError):calculate("2**100")
    def test_adapter_gate(self):
        from boitia.adapters import compare
        baseline={'results':[{'id':'a','passed':True},{'id':'b','passed':False}]}
        self.assertFalse(compare(baseline,baseline)['eligible'])
        self.assertTrue(compare(baseline,{'results':[{'id':'a','passed':True},{'id':'b','passed':True}]})['eligible'])
        self.assertFalse(compare(baseline,{'results':[{'id':'a','passed':False},{'id':'b','passed':True}]})['eligible'])
    def test_curate(self):
        q,a='Pregunta legítima','Respuesta revisada'
        h=hashlib.sha256(json.dumps([q,a],ensure_ascii=False).encode()).hexdigest();row={'conversations':[{'role':'user','content':q},{'role':'assistant','content':a}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.jsonl';p.write_text('\n'.join([json.dumps(row),json.dumps(row),'bad']))
            self.assertEqual(len(curate(p,set())[0]),0);accepted,rejected=curate(p,{h});self.assertEqual((len(accepted),rejected),(1,[2,3]))
            with self.assertRaises(ValueError):split(accepted)

if __name__=='__main__': unittest.main()
