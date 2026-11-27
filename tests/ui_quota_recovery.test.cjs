const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('frontend/index.html','utf8');
const state={},remoteCooldown=new Map(),root='https://boitia-ai.agustinwojtyszyn.com',ctx={Date,Math,Map,JSON,Error,URL,AbortSignal,state,remoteCooldown,persist(){},console,connected:true,health:{},localMode:false,remoteRoute:{provider:'cloudflare',root},uid:()=> 'req', $:()=>({}),portable:null};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function cooldownRemote('),html.indexOf('function conversationInstruction(')),ctx);
(async()=>{
 let sent=0;ctx.generateSharedAttempt=async(route,m,mode,ch)=>{sent++;if(route.provider==='cloudflare'){ch('parcial anterior');throw Object.assign(Error('daily'),{httpStatus:429,providerCode:'3036'})}ch('respuesta');return {text:'respuesta larga',finish_reason:'stop'}};
 ctx.connectPublic=async()=>{ctx.remoteRoute={provider:'kaggle',root:'https://example.trycloudflare.com'};ctx.connected=true;return true};
 const display=[];const answer=await ctx.generateSharedWithRecovery([], 'balanced',v=>display.push(v));
 assert.equal(sent,2);assert.equal(answer.text,'respuesta larga');assert.deepEqual(display,['parcial anterior','respuesta larga']);
 assert.equal(state.quotaUntil[root],Math.floor(Date.now()/86400000)*86400000+86400000);
 assert.equal(remoteCooldown.get(root),state.quotaUntil[root]);
 ctx.cooldownRemote({provider:'cloudflare',root}, {httpStatus:429,providerCode:'3040'});
 assert.equal(remoteCooldown.get(root),state.quotaUntil[root]); // temporary failure cannot shorten exhausted quota
 const other='https://other.trycloudflare.com';ctx.cooldownRemote({provider:'kaggle',root:other},{httpStatus:429});assert(remoteCooldown.get(other)<=Date.now()+60000);
 console.log('PASS: daily quota isolation, temporary errors, bounded failover, no duplicated partial text');
})().catch(e=>{console.error(e);process.exitCode=1});
