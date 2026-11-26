import assert from 'node:assert/strict';
import worker from '../deploy/cloudflare/worker.mjs';
import {SYSTEM_PROMPT,PROMPT_VERSION,FAST_PROMPT} from '../deploy/cloudflare/prompt.mjs';
const BASE='https://boitia-ai.test.workers.dev/api/boitia/v1';
const ORIGIN='https://agustinwojtyszyn.github.io';
let calls=0,quota=false,expectedBudget=32768;
const env={AI:{run:async(id,input)=>{
  calls++;
  assert.equal(id,'@cf/google/gemma-4-26b-a4b-it');
  assert.equal(input.messages[0].content,SYSTEM_PROMPT+(expectedBudget===8192?"\n"+FAST_PROMPT:""));
  assert.equal(input.max_completion_tokens,expectedBudget);
  assert.equal(input.stream,false);
  assert.deepEqual(input.chat_template_kwargs,{enable_thinking:false});
  if(quota)throw Error('3036 account quota');
  return {choices:[{message:{content:'<think>hidden</think>4',reasoning_content:'not public'},finish_reason:'stop'}]};
}}};
const req=(path,opts={})=>new Request(BASE+path,opts);
const health=await worker.fetch(req('/health',{headers:{Origin:ORIGIN}}),env);
assert.equal(health.status,200);const h=await health.json();assert.equal(h.prompt_version,PROMPT_VERSION);assert.deepEqual(h.max_tokens,{fast:8192,balanced:32768,deep:128000});assert.equal(calls,0);
const preflight=await worker.fetch(req('/chat/completions',{method:'OPTIONS',headers:{Origin:ORIGIN}}),env);
assert.equal(preflight.status,204);assert.equal(preflight.headers.get('Access-Control-Allow-Origin'),ORIGIN);
const body={model:'boitia',messages:[{role:'system',content:'untrusted'},{role:'user',content:'2+2'}],mode:'balanced',max_tokens:200000};
const send=(origin=ORIGIN,b=body)=>worker.fetch(req('/chat/completions',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','cf-connecting-ip':'192.0.2.1'},body:JSON.stringify(b)}),env);
assert.equal((await send('https://evil.example')).status,403);assert.equal(calls,0);
assert.equal((await send(ORIGIN,{...body,model:'arbitrary'})).status,400);assert.equal(calls,0);
const r=await send();assert.equal(r.status,200);const data=await r.json();
assert.equal(data.choices[0].message.content,'4');assert(!JSON.stringify(data).includes('hidden'));assert.equal(calls,1);
expectedBudget=8192;assert.equal((await send(ORIGIN,{...body,mode:'fast'})).status,200);
expectedBudget=128000;assert.equal((await send(ORIGIN,{...body,mode:'deep'})).status,200);
expectedBudget=32768;quota=true;const exhausted=await send();assert.equal(exhausted.status,429);assert.equal((await exhausted.json()).error.provider_code,'3036');
console.log('PASS: Cloudflare binding, prompt v'+PROMPT_VERSION+', origin, budget, no inference on health, quota error');

const encoder=new TextEncoder(),decoder=new TextDecoder();
let streamId=2;
async function streaming(parts){
  const env={AI:{run:async(id,input)=>{
    assert.equal(input.stream,true);assert.equal(input.max_completion_tokens,32768);
    return new ReadableStream({start(controller){for(const part of parts)controller.enqueue(encoder.encode(part));controller.close()}});
  }}};
  return worker.fetch(req('/chat/completions',{method:'POST',headers:{Origin:ORIGIN,'Content-Type':'application/json','cf-connecting-ip':'192.0.2.'+streamId++},body:JSON.stringify({...body,stream:true})}),env);
}
const event=(data)=>'data: '+JSON.stringify(data)+'\r\n\r\n';
const chunk=(content,finish_reason=null)=>event({choices:[{delta:{content,reasoning_content:'PRIVATE'},finish_reason}]});
const s=await streaming([chunk('<thi'),chunk('nk>hidden</th'),chunk('ink>Hola'),chunk(' mundo'),chunk('','length'),'data: [DONE]\r\n\r\n']);
assert.match(s.headers.get('content-type'),/text\/event-stream/);
const sText=await s.text();
assert.match(sText,/Hola/);assert.match(sText,/ mundo/);assert.match(sText,/"finish_reason":"length"/);assert.match(sText,/\[DONE\]/);
assert.doesNotMatch(sText,/PRIVATE|hidden|<think>/);
const legacy=await streaming(['data: {"response":"4"}\n','\ndata: [DONE]\n\n']);
assert.match(await legacy.text(),/"content":"4"/);
const interrupted=await streaming([chunk('Parcial')]);
const partial=await interrupted.text();assert.match(partial,/Parcial/);assert.match(partial,/"error"/);assert.doesNotMatch(partial,/\[DONE\]/);
const forbidden=await streaming([chunk('Hola <|chan'),chunk('nel|>secret'),'data: [DONE]\n\n']);
const blocked=await forbidden.text();assert.match(blocked,/Hola/);assert.match(blocked,/"error"/);assert.doesNotMatch(blocked,/secret|channel|\[DONE\]/);
// Prove delivery before the provider produces its terminal frame.
let sourceController;
const live=await worker.fetch(req('/chat/completions',{method:'POST',headers:{Origin:ORIGIN,'Content-Type':'application/json','cf-connecting-ip':'192.0.2.99'},body:JSON.stringify({...body,stream:true})}),{AI:{run:async()=>new ReadableStream({start(c){sourceController=c}})}});
const liveReader=live.body.getReader();
assert.match(decoder.decode((await liveReader.read()).value),/connected/);
sourceController.enqueue(encoder.encode(chunk('Primero')));
assert.match(decoder.decode((await liveReader.read()).value),/Primero/);
sourceController.enqueue(encoder.encode(chunk('','stop')+'data: [DONE]\n\n'));sourceController.close();
assert.match(decoder.decode((await liveReader.read()).value),/"finish_reason":"stop"/);
assert.match(decoder.decode((await liveReader.read()).value),/\[DONE\]/);
await liveReader.cancel();
console.log('PASS: Cloudflare real progressive delivery, reasoning filter, length, interrupted partial, legacy stream');
