import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from boitia.train import training_manifest, verify_run


class TrainingRunTests(unittest.TestCase):
    def test_resume_requires_same_manifest_and_checkpoint(self):
        args = SimpleNamespace(model='Qwen/Qwen2.5-1.5B-Instruct', max_length=768,
                               epochs=1, save_steps=10, seed=42)
        train = [{'sha256':'a'}]
        val = [{'sha256':'b'}]
        m = training_manifest(args, train, val, 1)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'version-1'
            verify_run(root,m,False)
            with self.assertRaises(ValueError): verify_run(root,m,False)
            with self.assertRaises(ValueError): verify_run(root,m,True)
            ckpt = root/'checkpoint-10'
            ckpt.mkdir()
            for name in ('trainer_state.json','adapter_model.safetensors','optimizer.pt','scheduler.pt'):
                (ckpt/name).write_text('{}')
            verify_run(root,m,True)
            for changed in (training_manifest(args,train,val,2),training_manifest(args,val,train,1)):
                with self.assertRaises(ValueError): verify_run(root,changed,True)

    def test_rollback_verifies_previous_digest(self):
        import json
        from boitia.adapters import adapter_digest, rollback
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            adapter=root/'candidate'
            adapter.mkdir()
            (adapter/'adapter_config.json').write_text('{}')
            (adapter/'adapter_model.safetensors').write_bytes(b'fixture')
            state=root/'state'
            state.mkdir()
            prev={'model':'test','adapter':str(adapter),'digest':adapter_digest(adapter),'decision':{'eligible':True}}
            (state/'previous.json').write_text(json.dumps(prev))
            (state/'active.json').write_text('{"model":"current"}')
            rollback(state)
            self.assertEqual(json.loads((state/'active.json').read_text()),prev)
            with self.assertRaises((ValueError,KeyError)): rollback(state)
