import unittest
from scripts.cloudflare_usage import summarize


class CloudflareUsageTests(unittest.TestCase):
    def test_aggregates_known_usage_without_claiming_invoice(self):
        rows=[{'count':2,'dimensions':{'modelId':'model-a','errorCode':0},
               'sum':{'totalNeurons':10,'totalInputTokens':100,'totalOutputTokens':200,
                      'totalInferenceTimeMs':600}},
              {'count':1,'dimensions':{'modelId':'model-a','errorCode':3036},
               'sum':{'totalNeurons':0,'totalInputTokens':0,'totalOutputTokens':0,
                      'totalInferenceTimeMs':0}}]
        x=summarize(rows)
        self.assertEqual(x['inferences'],3)
        self.assertEqual(x['errors'],1)
        self.assertEqual(x['neurons'],10)
        self.assertEqual(x['avg_inference_ms'],200)
        self.assertEqual(x['compute_equivalent_usd'],0.00011)
        self.assertNotIn('real_cost_usd',x)
