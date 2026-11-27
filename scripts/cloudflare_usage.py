"""Owner-only, read-only Cloudflare account analytics. Never returns credentials."""
import argparse
import json
import os
import re
import subprocess
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path


def summarize(rows):
    counts = {'inferences': 0, 'errors': 0, 'neurons': 0.0, 'input_tokens': 0.0,
              'output_tokens': 0.0, 'total_inference_ms': 0}
    models = {}
    for row in rows:
        count = int(row['count'])
        sums = row['sum']
        model = row['dimensions']['modelId']
        code = row['dimensions']['errorCode']
        counts['inferences'] += count
        counts['errors'] += count if code else 0
        counts['neurons'] += float(sums['totalNeurons'])
        counts['input_tokens'] += float(sums['totalInputTokens'])
        counts['output_tokens'] += float(sums['totalOutputTokens'])
        counts['total_inference_ms'] += int(sums['totalInferenceTimeMs'])
        models[model] = models.get(model, 0) + count
    counts['avg_inference_ms'] = (counts['total_inference_ms'] / counts['inferences']
                                  if counts['inferences'] else None)
    counts['models'] = models
    counts['compute_equivalent_usd'] = round(counts['neurons'] * .011 / 1000, 8)
    return counts


def query(account, token, start, end):
    if not re.fullmatch(r'[a-f0-9]{32}', account) or not re.fullmatch(r'[A-Za-z0-9_.~+/=-]+', token):
        raise ValueError('Cuenta o credencial no válida.')
    graphql = '''query($account: string!, $start: Time!, $end: Time!) {
      viewer { accounts(filter:{accountTag:$account}) {
        aiInferenceAdaptiveGroups(limit:100,filter:{datetime_geq:$start,datetime_lt:$end}) {
          count sum { totalNeurons totalInputTokens totalOutputTokens totalInferenceTimeMs }
          dimensions { modelId errorCode }
        }
      } }
    }'''
    # Use inline JSON-quoted values for compatibility with the provider's GraphQL scalar names.
    gql = graphql[graphql.index('{\n') + 1:]
    for name, value in [('account', account), ('start', start), ('end', end)]:
        gql = gql.replace('$'+name, json.dumps(value))
    payload = json.dumps({'query':'query {'+gql})
    r = subprocess.run(['curl','-sS','--max-time','25','--config','-',
                        '-H','Content-Type: application/json','--data',payload,
                        'https://api.cloudflare.com/client/v4/graphql'],
                       input='header = "Authorization: Bearer '+token+'"\n',
                       text=True, capture_output=True, check=True)
    data = json.loads(r.stdout)
    if data.get('errors') or not data.get('data'):
        raise RuntimeError('Cloudflare no devolvió métricas autorizadas.')
    accounts = data['data']['viewer']['accounts']
    if len(accounts) != 1:
        raise RuntimeError('Cuenta no disponible.')
    rows = accounts[0]['aiInferenceAdaptiveGroups']
    if len(rows) >= 100:
        raise RuntimeError('Respuesta posiblemente truncada; no se informa un total incompleto.')
    return summarize(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--account',default=os.environ.get('CLOUDFLARE_ACCOUNT_ID'))
    p.add_argument('--oauth',action='store_true',help='Utiliza la sesión Wrangler autorizada en este equipo')
    p.add_argument('--confirmed-free-plan',action='store_true')
    args = p.parse_args()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','')
    if args.oauth and not token:
        token=tomllib.loads((Path.home()/'.config/.wrangler/config/default.toml').read_text())['oauth_token']
    if not token or not args.account:
        p.error('Se requiere cuenta y autenticación autorizada.')
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0,minute=0,second=0,microsecond=0)
    month=day.replace(day=1)
    end=day+timedelta(days=1)
    fmt=lambda t:t.strftime('%Y-%m-%dT%H:%M:%SZ')
    daily=query(args.account,token,fmt(day),fmt(end))
    monthly=query(args.account,token,fmt(month),fmt(end))
    result={'scope':'provider_account_analytics_adaptive','as_of_utc':fmt(now),
            'daily':daily,'monthly':monthly,'real_cost_usd':None}
    if args.confirmed_free_plan:
        result['daily_quota_neurons']=10000
        result['daily_remaining_neurons']=max(0,10000-daily['neurons'])
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
