import asyncio
import sys
import types
import unittest
from unittest.mock import patch
import httpx
from frontend import boitia_server
from boitia.inference import Result

class FakeModel:
    config=types.SimpleNamespace(_name_or_path='test')
    def eval(self): return self

class ApiTests(unittest.TestCase):
    def test_poll_recovers_and_preserves_partial(self):
        fake=types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda:0,OutOfMemoryError=MemoryError,empty_cache=lambda:None))
        async def run():
            app=boitia_server.create_app(FakeModel(),None,'BoitIA')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                base=boitia_server.BASE
                body={'model':'boitia','messages':[{'role':'user','content':'Hola'}],'stream':True,'transport':'poll'}
                def partial(*args, **kwargs):
                    kwargs['on_text']('Respuesta parcial')
                    raise RuntimeError('test')
                async def submit(fn):
                    with patch.object(boitia_server,'respond',side_effect=fn) as mock:
                        r=await c.post(base+'/chat/completions',json=body)
                        self.assertEqual(r.status_code,202)
                        url=base+'/jobs/'+r.json()['job_id']
                        for _ in range(100):
                            status=(await c.get(url)).json()
                            if status['status']!='running':break
                            await asyncio.sleep(.01)
                        self.assertEqual(mock.call_count,1)
                        self.assertEqual((await c.get(url)).json(),status)
                        return url,status
                url,result=await submit(partial)
                self.assertEqual((result['status'],result['text']),('error','Respuesta parcial'))
                self.assertTrue((await c.delete(url)).json()['cancelled'])
                self.assertEqual((await c.get(url)).status_code,404)
                def complete(*args, **kwargs):
                    kwargs['on_text']('Bien')
                    return Result('Bien',2,1,0.1,'stop',.05,.08)
                _,result=await submit(complete)
                self.assertEqual((result['status'],result['text']),('done','Bien'))
                self.assertEqual(result['metrics']['ttft_seconds'],.05)
        with patch.dict(sys.modules,{'torch':fake}):asyncio.run(run())

    def test_portable_origin_is_opt_in(self):
        fake=types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda:0,OutOfMemoryError=MemoryError,empty_cache=lambda:None))
        async def run():
            with patch.dict('os.environ',{'BOITIA_PORTABLE_ORIGIN':'https://example.github.io'}):
                app=boitia_server.create_app(FakeModel(),None,'BoitIA')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                base=boitia_server.BASE
                origin='https://example.github.io'
                r=await c.get(base+'/health',headers={'Origin':origin})
                self.assertEqual(r.headers.get('access-control-allow-origin'),origin)
                r=await c.options(base+'/chat/completions',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
                self.assertEqual(r.status_code,200)
                r=await c.post(base+'/chat/completions',json={'model':'boitia','messages':[{'role':'user','content':'/calcular 2+2'}]},headers={'Origin':origin})
                self.assertEqual(r.status_code,200)
                r=await c.post(base+'/chat/completions',json={'model':'boitia','messages':[{'role':'user','content':'Hola'}]},headers={'Origin':'https://other.example'})
                self.assertEqual(r.status_code,403)
                self.assertNotIn('access-control-allow-origin',r.headers)
            with patch.dict('os.environ',{'BOITIA_PORTABLE_ORIGIN':'*'}):
                with self.assertRaises(ValueError):boitia_server.create_app(FakeModel(),None,'BoitIA')
        with patch.dict(sys.modules,{'torch':fake}):asyncio.run(run())

    def test_cpu_responder_and_serverless_limits(self):
        async def run():
            def cpu(*args,**kwargs):
                self.assertEqual(args[2],256)
                return Result("Respuesta CPU",2,3,1,"stop")
            app=boitia_server.create_app(None,None,'BoitIA',responder=cpu,model_info={"model":"CPU","usage_estimated":True},output_limit=256,allow_poll=False)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                base=boitia_server.BASE
                health=(await c.get(base+'/health')).json()
                self.assertEqual(health['gpu_count'],0);self.assertEqual(health['model'],"CPU");self.assertEqual(health['transport'],"sse")
                body={"model":"boitia","messages":[{"role":"user","content":"Hola"}],"mode":"deep"}
                r=await c.post(base+'/chat/completions',json={**body,"transport":"poll","stream":True})
                self.assertEqual(r.status_code,400)
                r=await c.post(base+'/chat/completions',json=body)
                self.assertEqual(r.status_code,200)
                self.assertTrue(r.json()['metrics']['usage_estimated'])
        asyncio.run(run())

    def test_routes_and_validation(self):
        fake=types.SimpleNamespace(cuda=types.SimpleNamespace(device_count=lambda:0,OutOfMemoryError=MemoryError,empty_cache=lambda:None))
        async def run():
            app=boitia_server.create_app(FakeModel(),None,'BoitIA')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                base=boitia_server.BASE
                self.assertEqual((await c.get(base+'/health')).json()['gpu_count'],0)
                self.assertEqual((await c.get('/')).status_code,200)
                body={'model':'boitia','messages':[{'role':'user','content':'Hola'}],'mode':'deep'}
                self.assertEqual((await c.post(base+'/chat/completions',json=body,headers={'origin':'https://other.example'})).status_code,403)
                self.assertEqual((await c.post(base+'/chat/completions',json={**body,'mode':'invalid'})).status_code,400)
                with patch.object(boitia_server,'respond',return_value=Result('Prueba',10,20,2,'length')) as mock:
                    r=await c.post(base+'/chat/completions',json=body)
                    self.assertEqual(r.status_code,200);self.assertEqual(r.json()['choices'][0]['finish_reason'],'length');self.assertEqual(r.json()['usage']['total_tokens'],30)
                    self.assertEqual(mock.call_args.args[3],'deep')
                r=await c.post(base+'/chat/completions',json={**body,'messages':[{'role':'user','content':'/calcular 0.1+0.2'}]})
                self.assertIn('3/10',r.json()['choices'][0]['message']['content'])
                def stream_stub(*args, **kwargs):
                    kwargs['on_text']('Hola ');kwargs['on_text']('mundo');return Result('Hola mundo',4,2,1,'stop')
                with patch.object(boitia_server,'respond',side_effect=stream_stub):
                    r=await c.post(base+'/chat/completions',json={**body,'stream':True})
                    self.assertIn('text/event-stream',r.headers['content-type']);self.assertIn('Hola ',r.text);self.assertIn('mundo',r.text);self.assertIn('[DONE]',r.text)
        with patch.dict(sys.modules,{'torch':fake}):asyncio.run(run())

if __name__=='__main__':unittest.main()
