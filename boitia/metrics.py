"""Ephemeral, privacy-preserving aggregate metrics for a single inference process."""
from datetime import datetime, timezone
from threading import Lock


class Metrics:
    def __init__(self):
        self.lock = Lock()
        self.buckets = {}

    def _current(self, now):
        keys = (now.strftime('%Y-%m-%d'), now.strftime('%Y-%m'))
        self.buckets = {k: self.buckets.get(k, {
            'requests': 0, 'completed': 0, 'errors': 0, 'cancelled': 0,
            'input_tokens': 0, 'output_tokens': 0, 'known_token_requests': 0,
            'generation_seconds': 0.0, 'latency_samples': 0,
        }) for k in keys}
        return keys

    def record(self, status, result=None):
        with self.lock:
            for k in self._current(datetime.now(timezone.utc)):
                b = self.buckets[k]
                b['requests'] += 1
                b[status] += 1
                if result is not None:
                    b['input_tokens'] += int(result.input_tokens)
                    b['output_tokens'] += int(result.output_tokens)
                    b['known_token_requests'] += 1
                    b['generation_seconds'] += float(result.elapsed)
                    b['latency_samples'] += 1

    def snapshot(self):
        with self.lock:
            day, month = self._current(datetime.now(timezone.utc))
            def report(key):
                b = dict(self.buckets[key])
                b['avg_generation_seconds'] = (b['generation_seconds'] /
                    b['latency_samples']) if b['latency_samples'] else None
                return {'period_utc': key, **b}
            return {'daily': report(day), 'monthly': report(month),
                    'scope': 'single_process_since_start', 'provider_quota': None,
                    'real_cost_usd': None}
