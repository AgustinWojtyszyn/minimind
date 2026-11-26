import base64
import io
import json
import unittest
from boitia.registry import publish_engine, validate_tunnel, validate_provider_url, REGISTRY_API

class RegistryTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_tunnel("https://demo.trycloudflare.com"),"https://demo.trycloudflare.com")
        for url in ("https://evil.example","https://x.trycloudflare.com/path","https://x.trycloudflare.com@evil.example"):
            with self.assertRaises(ValueError): validate_tunnel(url)

    def test_remote_publication_preserves_existing_backends(self):
        calls=[]
        old={"version":1,"kaggle_url":"https://old.trycloudflare.com","zerogpu_url":"https://owner-app.hf.space"}
        class Opener:
            def open(self,request,timeout):
                calls.append(request)
                if request.method=="GET":
                    return io.BytesIO(json.dumps({"sha":"abc","content":base64.b64encode(json.dumps(old).encode()).decode()}).encode())
                return io.BytesIO(b"{}")
        self.assertTrue(publish_engine("https://boitia.agustinwojtyszyn.com","secret",provider="cpu",opener=Opener()))
        doc=json.loads(base64.b64decode(json.loads(calls[-1].data)["content"]))
        self.assertEqual(doc["kaggle_url"],old["kaggle_url"])
        self.assertEqual(doc["zerogpu_url"],old["zerogpu_url"])
        self.assertEqual(doc["cpu_url"],"https://boitia.agustinwojtyszyn.com")
        for provider,url in (("modal","https://owner--app.modal.run/path"),("zerogpu","https://evil.example"),("cpu","https://example.com")):
            with self.assertRaises(ValueError):validate_provider_url(provider,url)

    def test_publication_has_no_secrets(self):
        calls=[]
        class Opener:
            def open(self,request,timeout):
                calls.append(request)
                if request.method=="GET":
                    return io.BytesIO(json.dumps({"sha":"abc","content":base64.b64encode(b'{"version":1,"kaggle_url":null}').decode()}).encode())
                return io.BytesIO(b'{}')
        self.assertTrue(publish_engine("https://demo.trycloudflare.com","secret-test",opener=Opener()))
        self.assertEqual(calls[0].full_url,REGISTRY_API+"?ref=master")
        self.assertEqual(calls[1].full_url,REGISTRY_API)
        body=json.loads(calls[1].data)
        self.assertEqual(body["branch"],"master")
        self.assertEqual(body["sha"],"abc")
        doc=json.loads(base64.b64decode(body["content"]))
        self.assertEqual(set(doc),{"version","kaggle_url","updated_at"})
        self.assertNotIn("secret-test",json.dumps(doc))

if __name__=="__main__":unittest.main()
