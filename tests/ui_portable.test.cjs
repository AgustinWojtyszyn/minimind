const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=readFileSync('frontend/index.html','utf8');
const elements={status:{},engine:{},error:{}};
let localCalls=0,remoteCalls=[],remoteReady=false;
let registry={version:1,kaggle_url:'https://shared-tunnel.trycloudflare.com'};
const ctx={URL,AbortSignal,Error,JSON,state:{localEnabled:false,portableKaggle:'https://old-user-tunnel.trycloudflare.com'},
  connected:false,connecting:false,localMode:false,publicMode:false,health:null,apiModel:'boitia',PUBLIC_API:'',
  portable:{init:async()=>{localCalls++;return {model:'test-local',device:'wasm'}}},
  refreshStatus:()=>{},$:k=>elements[k],
  fetch:async(url)=>{remoteCalls.push(url);if(url==='engine.json')return {ok:true,json:async()=>registry};return {ok:remoteReady,json:async()=>({ready:true,busy:false,model:'test-remote'})}}};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function validKaggle('),html.indexOf('function refreshStatus()')),ctx);
(async()=>{
 assert.equal(await ctx.connectPublic(),false);assert.equal(localCalls,0);
 assert.deepEqual(remoteCalls,['engine.json','https://shared-tunnel.trycloudflare.com/api/boitia/v1/health']);
 // A fresh visitor requires neither a local preference nor credentials.
 ctx.state={};remoteReady=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.publicMode,true);assert.equal(localCalls,0);
 registry={version:1,kaggle_url:'https://new-tunnel.trycloudflare.com'};
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.PUBLIC_API,'https://new-tunnel.trycloudflare.com/api/boitia/v1');
 remoteReady=false;ctx.state.localEnabled=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.localMode,true);assert.equal(localCalls,1);
 registry={version:1,kaggle_url:'https://evil.test'};ctx.state={};remoteCalls=[];
 assert.equal(await ctx.connectPublic(),false);assert.deepEqual(remoteCalls,['engine.json']);
 for(const invalid of ['http://my-tunnel.trycloudflare.com','https://evil.test','https://my-tunnel.trycloudflare.com/path','https://user@my-tunnel.trycloudflare.com'])assert.throws(()=>ctx.validKaggle(invalid));
 assert(!html.includes('Guardar túnel Kaggle'));
 console.log('PASS: fresh visitor auto-connects, rotation without user input, owner-only registry, optional fallback');
})().catch(e=>{console.error(e);process.exitCode=1});
