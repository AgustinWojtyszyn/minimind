"""Compare actual benchmark reports; no automatic model promotion."""
import argparse
import json
from pathlib import Path


def compare(base, candidate, latency_ratio=1.5):
    a = {r['id']: r for r in base['results']}
    b = {r['id']: r for r in candidate['results']}
    if not a or a.keys() != b.keys() or base['mode'] != candidate['mode'] or base.get('devices') != candidate.get('devices'):
        return {'eligible': False, 'reason': 'Different cases, mode or hardware'}
    regressions = [k for k in a if a[k]['passed'] and not b[k]['passed']]
    gains = [k for k in a if not a[k]['passed'] and b[k]['passed']]
    errors = [k for k in b if 'error' in b[k] or b[k].get('finish_reason') == 'length' and a[k].get('finish_reason') != 'length']
    ratios = {}
    for metric in ('wall_seconds', 'request_first_visible_seconds'):
        old, new = base.get('summary', {}).get(metric), candidate.get('summary', {}).get(metric)
        if old is not None and old > 0 and new is not None:
            ratios[metric] = new / old
    latency_ok = len(ratios) == 2 and all(v <= latency_ratio for v in ratios.values())
    return {'eligible': bool(gains) and not regressions and not errors and latency_ok,
            'gains': gains, 'regressions': regressions, 'errors': errors,
            'latency_ratios': ratios, 'max_ratio': latency_ratio,
            'requires_owner_review': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline')
    parser.add_argument('candidate')
    parser.add_argument('--max-latency-ratio', type=float, default=1.5)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(Path(args.baseline).read_text()),
                             json.loads(Path(args.candidate).read_text()), args.max_latency_ratio), indent=2))
