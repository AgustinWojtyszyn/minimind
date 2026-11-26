// Node-only regression of the actual frontend transport and submit handlers.
const {readFileSync}=require('fs'), vm=require('vm'), assert=require('assert/strict');
const html=readFileSync('frontend/index.html','utf8');
const start=html.indexOf('function requestMessages(');
const end=html.indexOf("setInterval(()=>",start);
const elements={prompt:{value:'Hola'},error:{textContent:'Error previo'},composer:{}};
const c={messages:[]}; let posts=0,polls=0, renders=0;
const ctx={c, elements, PUBLIC_API:'/api/boitia/v1',connected:true,publicMode:true,busy:false,apiModel:'boitia',health:{profiles:{},transport:'poll'},state:{intelligence:'balanced'}, AbortSignal, Date, JSON, Error, Object, performance,
  $:k=>elements[k],chat:()=>c,relevantMemories:()=>[],persist:()=>{}, renderHistory:()=>{},render:()=>renders++,refreshStatus:()=>{},sleep:async()=>{},connectPublic:async()=>{ctx.connected=true;ctx.health={profiles:{},transport:'poll'};return true},
  fetch:async(url,options)=>{
    if(options.method==='POST'){posts++;if(posts===1)throw Error('network error');return {ok:true,json:async()=>({job_id:'id'})}}
    if(options.method==='DELETE')return {ok:true};
    polls++;if(polls===1)throw Error('network error');
    return {ok:true,json:async()=>polls===2?{status:'running',text:'Hola '}:{status:'done',text:'Hola mundo',finish_reason:'stop'}};
  }};
vm.createContext(ctx);
vm.runInContext(html.slice(start,end),ctx);
(async()=>{
  await elements.composer.onsubmit({preventDefault(){}});
  assert.match(elements.error.textContent,/network error/);assert.equal(c.messages.length,0);assert.equal(elements.prompt.value,'Hola');
  await elements.composer.onsubmit({preventDefault(){}});
  assert.equal(elements.error.textContent,'');assert.equal(c.messages.length,2);
  assert.equal(c.messages[1].content,'Hola mundo');assert.equal(posts,2);assert.equal(polls,3);
  assert.equal(ctx.busy,false); console.log('PASS: actual frontend submit, recovery, no duplicate or residual errors');
})().catch(e=>{console.error(e);process.exitCode=1});
