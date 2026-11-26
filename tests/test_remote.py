import io
import json
import unittest
from boitia.cpu_inference import CPUResponder
from boitia.remote_verify import verify_remote

class RemoteTests(unittest.TestCase):
    def test_cpu_stream(self):
        class LLM:
            def tokenize(self,text,add_bos=False):return list(text)
            def create_chat_completion(self,**opts):
                self.opts=opts
                yield {"choices":[{"delta":{"content":"Cuatro"},"finish_reason":None}]}
                yield {"choices":[{"delta":{},"finish_reason":"stop"}]}
        llm=LLM();chunks=[]
        result=CPUResponder(llm)([{"role":"system","content":"Sistema"},{"role":"user","content":"2+2"}],"balanced",512,.3,on_text=chunks.append)
        self.assertEqual(result.text,"Cuatro");self.assertEqual(chunks,["Cuatro"])
        self.assertEqual(llm.opts["max_tokens"],256)

    def test_remote_verification(self):
        class Response(io.BytesIO):
            headers={"Access-Control-Allow-Origin":"https://agustinwojtyszyn.github.io"}
        class Opener:
            def __init__(self):self.methods=[]
            def open(self,req,timeout):
                self.methods.append(req.method)
                if req.method=="OPTIONS":return Response(b"")
                if req.method=="POST":return Response(b'{"event_id":"ok"}')
                return Response(b'event: complete\ndata: [{"text":"4"}]\n\n')
        opener=Opener()
        self.assertEqual(verify_remote("zerogpu","https://owner-boitia.hf.space",opener=opener),"4")
        self.assertEqual(opener.methods,["OPTIONS","POST","GET"])
        class BadOpener:
            def open(self,req,timeout):
                r=Response(b"");r.headers={};return r
        with self.assertRaises(RuntimeError):verify_remote("zerogpu","https://owner-boitia.hf.space",opener=BadOpener())

if __name__=="__main__":unittest.main()
