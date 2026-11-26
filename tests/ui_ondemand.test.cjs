const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=readFileSync('frontend/index.html','utf8');
const calls=[];let fail=false;
const ctx={URL,AbortSignal,Error,JSON,TextDecoder,TextEncoder,Uint8Array,encodeURIComponent,
  readStream:async(r,onChunk)=>{onChunk('4');return 'stop'},
  fetch:async(url,opts)=>{
    calls.push({url,opts});
    if(url.endsWith('/chat/completions'))return {ok:true};
    if(opts.method==='POST')return {ok:true,json:async()=>({event_id:'valid-id'})};
    const stream=new TextEncoder().encode(fail?'event: error\ndata: null\n\n':'event: heartbeat\ndata: null\n\nevent: complete\ndata: [{"text":"4","finish_reason":"stop"}]\n\n');
    let read=0;return {ok:true,body:{getReader:()=>({read:async()=>read++?{done:true}:{done:false,value:stream},cancel:async()=>{}})}};
  }};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('async function generateOnDemand('),html.indexOf("$('composer').onsubmit=")),ctx);
(async()=>{
 const messages=[{role:'user',content:'2+2'}];let text='';
 const modal=await ctx.generateOnDemand({provider:'modal',root:'https://owner--app.modal.run'},messages,'fast',x=>text=x);
 assert.equal(modal.text,'4');assert.equal(text,'4');assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0].opts.body).stream,true);
 calls.length=0;text='';
 const zero=await ctx.generateOnDemand({provider:'zerogpu',root:'https://owner-boitia.hf.space'},messages,'fast',x=>text=x);
 assert.equal(zero.text,'4');assert.equal(text,'4');assert.equal(calls.length,2);
 fail=true;calls.length=0;
 await assert.rejects(ctx.generateOnDemand({provider:'zerogpu',root:'https://owner-boitia.hf.space'},messages,'fast',()=>{}),/cuota/);
 assert.equal(calls.filter(x=>x.opts.method==='POST').length,1);
 console.log('PASS: Modal SSE, ZeroGPU queue result, no duplicate POST on error');
})().catch(e=>{console.error(e);process.exitCode=1});
