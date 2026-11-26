const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=readFileSync('frontend/index.html','utf8');
const elements={status:{},engine:{},error:{}};
let localCalls=0,remoteCalls=[],remoteReady=false;
let registry={version:1,kaggle_url:'https://shared-tunnel.trycloudflare.com'};
const ctx={URL,AbortSignal,Error,JSON,Date,Map,state:{localEnabled:false,portableKaggle:'https://old-user-tunnel.trycloudflare.com'},
  connected:false,connecting:false,localMode:false,publicMode:false,health:null,apiModel:'boitia',PUBLIC_API:'',remoteRoute:null,remoteCooldown:new Map(),
  portable:{init:async()=>{localCalls++;return {model:'test-local',device:'wasm'}}},
  refreshStatus:()=>{},$:k=>elements[k],
  fetch:async(url)=>{remoteCalls.push(url);if(url==='engine.json')return {ok:true,json:async()=>registry};return {ok:remoteReady,json:async()=>({ready:true,busy:false,model:'test-remote'})}}};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function validKaggle('),html.indexOf('function refreshStatus()')),ctx);
(async()=>{
 assert.equal(await ctx.connectPublic(),false);assert.equal(localCalls,0);
 assert.deepEqual(remoteCalls,['engine.json','https://shared-tunnel.trycloudflare.com/api/boitia/v1/health']);
 ctx.state={};remoteReady=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.publicMode,true);assert.equal(localCalls,0);
 registry={version:1,kaggle_url:'https://new-tunnel.trycloudflare.com'};
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.PUBLIC_API,'https://new-tunnel.trycloudflare.com/api/boitia/v1');
 // On-demand services are configured, never woken by discovery or periodic health checks.
 registry.modal_url='https://owner--boitia-serve.modal.run';registry.zerogpu_url='https://owner-boitia.hf.space';
 registry.cloudflare_url='https://boitia-ai.owner.workers.dev';
 remoteReady=false;remoteCalls=[];
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.remoteRoute.provider,'cloudflare');
 assert.deepEqual(remoteCalls,['engine.json','https://new-tunnel.trycloudflare.com/api/boitia/v1/health']);
 ctx.remoteCooldown.set(registry.cloudflare_url,Date.now()+60000);
 remoteReady=false;remoteCalls=[];
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.remoteRoute.provider,'modal');assert.equal(ctx.health.onDemand,true);
 assert.deepEqual(remoteCalls,['engine.json','https://new-tunnel.trycloudflare.com/api/boitia/v1/health']);
 ctx.remoteCooldown.set(registry.modal_url,Date.now()+60000);
 remoteCalls=[];
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.remoteRoute.provider,'zerogpu');
 assert.deepEqual(remoteCalls,['engine.json','https://new-tunnel.trycloudflare.com/api/boitia/v1/health']);
 ctx.remoteCooldown.set(registry.zerogpu_url,Date.now()+60000);
 registry.cpu_url='https://boitia.agustinwojtyszyn.com';remoteReady=true;ctx.remoteCooldown.set(registry.kaggle_url,Date.now()+60000);
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.remoteRoute.provider,'cpu');
 remoteReady=false;ctx.state.localEnabled=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.localMode,true);assert.equal(localCalls,1);
 registry={version:1,kaggle_url:'https://evil.test',modal_url:'https://evil.test'};ctx.state={};remoteCalls=[];
 assert.equal(await ctx.connectPublic(),false);assert.deepEqual(remoteCalls,['engine.json']);
 for(const invalid of ['http://my-tunnel.trycloudflare.com','https://evil.test','https://my-tunnel.trycloudflare.com/path','https://user@my-tunnel.trycloudflare.com'])assert.throws(()=>ctx.validKaggle(invalid));
 assert.equal(ctx.validRemote('cloudflare','https://boitia-ai.agustinwojtyszyn.com'),'https://boitia-ai.agustinwojtyszyn.com');
 assert.throws(()=>ctx.validRemote('cloudflare','https://agustinwojtyszyn.com'));
 assert.throws(()=>ctx.validRemote('zerogpu','https://owner-boitia.hf.space/path'));
 assert(!html.includes('Guardar túnel Kaggle'));
 console.log('PASS: shared route rotation, deterministic fallback, no background GPU wake, opt-in local');
})().catch(e=>{console.error(e);process.exitCode=1});
