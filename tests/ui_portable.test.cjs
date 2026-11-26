const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=readFileSync('frontend/index.html','utf8');
const elements={status:{},engine:{},error:{}};
let localCalls=0,remoteCalls=0,remoteReady=false;
const ctx={URL,AbortSignal,Error,JSON,state:{localEnabled:false,portableKaggle:'https://my-tunnel.trycloudflare.com'},
  connected:false,connecting:false,localMode:false,publicMode:false,health:null,apiModel:'boitia',PUBLIC_API:'',
  portable:{init:async()=>{localCalls++;return {model:'test-local',device:'wasm'}}},
  refreshStatus:()=>{},$:k=>elements[k],
  fetch:async()=>{remoteCalls++;return {ok:remoteReady,json:async()=>({ready:true,busy:false,model:'test-remote'})}}};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function validKaggle('),html.indexOf('function refreshStatus()')),ctx);
(async()=>{
 assert.equal(await ctx.connectPublic(),false);assert.equal(localCalls,0);
 ctx.state.localEnabled=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.localMode,true);assert.equal(localCalls,1);
 remoteReady=true;
 assert.equal(await ctx.connectPublic(),true);assert.equal(ctx.publicMode,true);assert.equal(ctx.localMode,false);assert.equal(localCalls,1);
 for(const invalid of ['http://my-tunnel.trycloudflare.com','https://evil.test','https://my-tunnel.trycloudflare.com/path','https://user@my-tunnel.trycloudflare.com'])assert.throws(()=>ctx.validKaggle(invalid));
 console.log('PASS: no download without consent, local fallback, remote priority, strict URL');
})().catch(e=>{console.error(e);process.exitCode=1});
