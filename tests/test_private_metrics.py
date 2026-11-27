import asyncio
import os
import unittest
from unittest.mock import patch
import httpx
from frontend.boitia_server import create_app, BASE
from boitia.inference import Result


class PrivateMetricsTests(unittest.TestCase):
    def test_authentication_and_anonymized_counts(self):
        async def run():
            token = 'test-token-' + 'x'*32
            def responder(*args, **kwargs):
                return Result('private response', 12, 6, 0.2, 'stop')
            with patch.dict(os.environ, {'BOITIA_ADMIN_TOKEN': token}):
                app = create_app(None, None, 'Boiti', responder=responder,
                                 model_info={'model':'fixture','usage_estimated': True})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                endpoint=BASE+'/admin/metrics'
                self.assertEqual((await c.get(endpoint)).status_code,401)
                self.assertEqual((await c.get(endpoint,headers={'Authorization':'Bearer invalid'})).status_code,401)
                self.assertEqual((await c.post(BASE+'/chat/completions',json={'model':'boitia','messages':[{'role':'user','content':'private prompt'}]})).status_code,200)
                r=await c.get(endpoint,headers={'Authorization':'Bearer '+token})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.json()['daily']['completed'],1)
                self.assertEqual(r.json()['monthly']['input_tokens'],12)
                self.assertTrue(r.json()['usage_estimated'])
                self.assertNotIn('private prompt',r.text)
                self.assertNotIn('private response',r.text)
                self.assertNotIn(token,r.text)
                self.assertIsNone(r.json()['real_cost_usd'])
            with patch.dict(os.environ, {'BOITIA_ADMIN_TOKEN': ''}):
                app=create_app(None,None,'Boiti',responder=responder)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                self.assertEqual((await c.get(BASE+'/admin/metrics')).status_code,404)
        asyncio.run(run())
