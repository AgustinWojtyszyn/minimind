"""Optional real Chromium test; uses simulated API, never real model or internet."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = (Path(__file__).resolve().parents[1] / 'frontend/index.html').read_text()
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 393, 'height': 873}, is_mobile=True, has_touch=True)
    calls={'post':0,'poll':0}
    def route(r):
        path=r.request.url.split('https://boitia.test')[-1]
        if path=='/':
            r.fulfill(status=200,content_type='text/html',body=HTML)
        elif path.endswith('/health'):
            r.fulfill(json={'ready':True,'model':'test','profiles':{'balanced':{}},'transport':'poll'})
        elif path.endswith('/chat/completions'):
            calls['post']+=1
            if calls['post']==1:r.abort('failed')
            else:r.fulfill(status=202,json={'job_id':'fake-job'})
        elif path.endswith('/jobs/fake-job'):
            calls['poll']+=1
            if calls['poll']==1:r.abort('failed')
            elif calls['poll']==2:r.fulfill(json={'status':'running','text':'Hola '})
            else:r.fulfill(json={'status':'done','text':'Hola mundo','finish_reason':'stop'})
        else:r.fulfill(status=404)
    page.route('https://boitia.test/**',route)
    page.goto('https://boitia.test/')
    page.wait_for_function("document.querySelector('#status').textContent==='Motor conectado'")
    page.evaluate("""() => {state.memories.push({id:'m',text:'Kiara'}); state.lessons.push({id:'l',question:'Q',answer:'A'});persist()}""")
    page.locator('#prompt').fill('Hola')
    page.locator('#send').click()
    page.wait_for_function("document.querySelector('#error').textContent.includes('No se recibió')")
    page.wait_for_function("!document.querySelector('#send').disabled")
    assert page.locator('#prompt').input_value()=='Hola'
    page.locator('#send').click()
    page.wait_for_function("document.querySelector('#error').textContent===''")
    page.wait_for_function("Array.from(document.querySelectorAll('.msg.assistant')).some(x=>x.textContent.includes('Hola mundo'))")
    page.wait_for_function("!document.querySelector('#send').disabled")
    assert page.locator('#error').inner_text()==''
    assert page.locator('.msg.user').count()==1
    assert page.locator('.msg.assistant').count()==1
    assert calls=={'post':2,'poll':3},calls
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.reload()
    page.wait_for_function("document.querySelector('.msg.assistant')?.textContent.includes('Hola mundo')")
    assert page.evaluate("state.memories.length===1 && state.lessons.length===1")
    print('PASS: mobile viewport, failed POST, retry, transient poll failure, no residual error or duplicated turn, persisted chat/memory/lesson')
    browser.close()
