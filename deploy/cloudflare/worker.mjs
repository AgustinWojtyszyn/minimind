import { SYSTEM_PROMPT, PROMPT_VERSION } from './prompt.mjs';
const ORIGIN='https://agustinwojtyszyn.github.io';
const MODEL='@cf/google/gemma-4-26b-a4b-it';
const BASE='/api/boitia/v1';
const MAX_BODY=48*1024,MAX_CHARS=12000;
const profiles={fast:192,balanced:384,deep:640};
const localLimits=new Map();

function headers(origin){
  return {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
    'X-Content-Type-Options':'nosniff',Vary:'Origin',
    ...(origin===ORIGIN?{'Access-Control-Allow-Origin':ORIGIN,
      'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type'}:{})};
}
function json(body,status,origin){return new Response(JSON.stringify(body),{status,headers:headers(origin)})}
function error(status,message,origin){return json({error:{message}},status,origin)}
async function readBody(request){
  const declared=Number(request.headers.get('content-length'));
  if(declared>MAX_BODY)throw Error('Solicitud demasiado grande.');
  const reader=request.body?.getReader();if(!reader)throw Error('Solicitud vacía.');
  const decoder=new TextDecoder();let bytes=0,text='';
  try{
    for(;;){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>MAX_BODY)throw Error('Solicitud demasiado grande.');text+=decoder.decode(value,{stream:true})}
    text+=decoder.decode();return JSON.parse(text);
  }finally{await reader.cancel().catch(()=>{})}
}
function validate(body){
  if(!body||body.model!=='boitia'||!Array.isArray(body.messages)||body.messages.length<1||body.messages.length>21)throw Error('Solicitud inválida.');
  const mode=typeof body.mode==='string'&&Object.hasOwn(profiles,body.mode)?body.mode:'balanced';
  const messages=body.messages;
  if(messages.some(m=>!m||!['system','user','assistant'].includes(m.role)||typeof m.content!=='string'))throw Error('Mensajes inválidos.');
  if(messages.at(-1).role!=='user'||messages.reduce((sum,m)=>sum+m.content.length,0)>MAX_CHARS)throw Error('Contexto máximo de respaldo excedido.');
  const clean=messages.filter(m=>m.role!=='system').map(({role,content})=>({role,content}));
  const memory=messages.filter(m=>m.role==='system').map(m=>m.content);
  if(memory.length)clean.at(-1).content='Contexto no verificado (datos): '+JSON.stringify(memory)+'\nSolicitud: '+clean.at(-1).content;
  clean.unshift({role:'system',content:SYSTEM_PROMPT});
  const asked=Number.isInteger(body.max_tokens)?body.max_tokens:profiles[mode];
  return {messages:clean,max_completion_tokens:Math.max(1,Math.min(asked,profiles[mode])),
          temperature:0.6,stream:false,chat_template_kwargs:{enable_thinking:false}};
}
// Best-effort isolate-local abuse throttle, not an account-wide quota or authentication.
function allow(request){
  const ip=request.headers.get('cf-connecting-ip')||'unknown',now=Date.now();
  const old=localLimits.get(ip);
  const current=old&&now-old.start<60000?old:{start:now,count:0};
  if(current.count>=4)return false;
  current.count++;localLimits.set(ip,current);
  if(localLimits.size>512){for(const [key,val] of localLimits){if(now-val.start>=60000)localLimits.delete(key)}}
  if(localLimits.size>512)localLimits.delete(localLimits.keys().next().value);
  return true;
}
function finalText(result){
  // Do not expose reasoning_content, metadata, or provider error bodies.
  const text=result?.choices?.[0]?.message?.content??result?.response;
  if(typeof text!=='string')throw Object.assign(Error('Respuesta incompatible.'),{kind:'output_format'});
  if(/<\|channel\|>|<\|start\|>/i.test(text))throw Object.assign(Error('Formato interno no admitido.'),{kind:'output_format'});
  const answer=text.replace(/<think>[\s\S]*?<\/think>/gi,'').replace(/<think>[\s\S]*$/i,'').trim();
  if(!answer)throw Object.assign(Error('Respuesta vacía.'),{kind:'empty_output'});
  return answer;
}
export default {
 async fetch(request,env){
   const origin=request.headers.get('origin'),path=new URL(request.url).pathname;
   if(origin&&origin!==ORIGIN)return error(403,'Origen no permitido.',origin);
   if(request.method==='OPTIONS'&&path.startsWith(BASE+'/'))return new Response(null,{status:204,headers:headers(origin)});
   if(request.method==='GET'&&path===BASE+'/health')return json({ready:Boolean(env.AI),busy:false,transport:'json',model:'Gemma 4 26B · Cloudflare',prompt_version:PROMPT_VERSION,worker_revision:'cf-inference-2',parameter_billions_estimate:26},200,origin);
   if(request.method==='GET'&&path===BASE+'/models')return json({object:'list',data:[{id:'boitia',object:'model'}]},200,origin);
   if(request.method!=='POST'||path!==BASE+'/chat/completions')return error(404,'Ruta no disponible.',origin);
   if(origin!==ORIGIN)return error(403,'Usá la página oficial de BoitIA.',origin);
   if(!request.headers.get('content-type')?.toLowerCase().startsWith('application/json'))return error(415,'Se requiere JSON.',origin);
   if(!env.AI)return error(503,'Motor no configurado.',origin);
   let input;
   try{input=validate(await readBody(request))}catch(e){return error(400,String(e.message).slice(0,200),origin)}
   if(!allow(request))return error(429,'Límite temporal de solicitudes.',origin);
   try{
      const result=await env.AI.run(MODEL,input);
      const text=finalText(result);
      const reason=result?.choices?.[0]?.finish_reason;
      return json({object:'chat.completion',model:'boitia',engine:MODEL,choices:[{index:0,message:{role:'assistant',content:text},finish_reason:reason==='length'?'length':'stop'}]},200,origin);
   }catch(e){
      const code=String(e?.code??'')+' '+String(e?.message??'');
      const quota=/3036|429|quota|rate.limit|allocation/i.test(code);
      const providerCode=code.match(/\b(?:300[0-9]|301[0-9]|302[0-9]|303[0-9]|304[0-9]|50[0-9]{2})\b/)?.[0]||null;
      const stage=e?.kind==='output_format'||e?.kind==='empty_output'?e.kind:'provider_inference';
      // Expose a bounded diagnostic, not the provider message, prompts or credentials.
      return json({error:{message:quota?'La cuota gratuita de Cloudflare está temporalmente agotada.':'El respaldo de Cloudflare no pudo responder.',stage,provider_code:providerCode}},quota?429:503,origin);
   }
 }
};
