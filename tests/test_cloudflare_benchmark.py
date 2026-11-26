import unittest
from scripts.benchmark_cloudflare import measure


class BenchmarkTest(unittest.TestCase):
    def test_measures_first_visible_not_heartbeat(self):
        lines = [
            ': connected\n', '\n',
            'data: {"choices":[{"delta":{"content":" "}}]}\n',
            'data: {"choices":[{"delta":{"content":"Hola mundo"}}]}\n',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n',
            'data: [DONE]\n',
        ]
        times = iter([12.5, 15.0])
        result = measure(lines, 10.0, lambda: next(times))
        self.assertEqual(result["primer_texto_s"], 2.5)
        self.assertEqual(result["total_s"], 5.0)
        self.assertEqual(result["palabras"], 2)

    def test_rejects_partial(self):
        with self.assertRaises(RuntimeError):
            measure(['data: {"choices":[{"delta":{"content":"Parcial"}}]}\n'], 0, lambda: 1)
