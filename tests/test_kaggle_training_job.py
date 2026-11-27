import json
import tempfile
import unittest
from pathlib import Path
from scripts.prepare_kaggle_training import prepare, MODEL_IDS


class KaggleTrainingJobTests(unittest.TestCase):
    def test_private_pinned_gpu_job(self):
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)/'job'
            prepare(job,'owner/boiti-train','owner/approved-data','a'*40,MODEL_IDS[0],1,2)
            m=json.loads((job/'kernel-metadata.json').read_text())
            self.assertTrue(m['is_private'])
            self.assertTrue(m['enable_gpu'])
            self.assertEqual(m['dataset_sources'],['owner/approved-data'])
            source=(job/'train.py').read_text()
            self.assertIn('approved.sha256',source)
            self.assertIn('a'*40,source)
            self.assertIn('torch.distributed.run',source)
            compile(source,'train.py','exec')
