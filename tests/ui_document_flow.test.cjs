const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('frontend/index.html','utf8');
const src=fs.readFileSync('frontend/portable/tools.js','utf8');
const prompt='Dame un PDF con tres recetas de pollo';
const boilerplate='Como soy un modelo de lenguaje, no puedo generar ni entregarte un archivo descargable directamente (como un PDF).\n\nAcá tenés el contenido:\n\n---\n\n# Recetario\nPollo al horno con papas y limón.';
const c={messages:[]},elements={prompt:{value:prompt},composer:{},error:{textContent:''}};
const el=(tag,cls,text)=>({tag,cls,text,children:[],append(...children){this.children.push(...children)}});
let posted=null, downloads=[];
const ctx={TextEncoder,TextDecoder,AbortSignal,Date,JSON,Error,Object,performance,Blob,URLSearchParams,
  c, PUBLIC_API:'/api/boitia/v1', connected:true,publicMode:true,busy:false,apiModel:'boitia',health:{profiles:{}},state:{intelligence:'balanced'}, attachedFile:null,
  $:k=>elements[k],chat:()=>c,relevantMemories:()=>[],persist:()=>{},render:()=>{},renderHistory:()=>{},refreshStatus:()=>{},clearAttached:()=>{},
  el,btn:(label,fn)=>({label,fn}),download:(name,data,type)=>downloads.push({name,data,type}),alert:e=>{throw Error(e)},
  fetch:async(_url,opts)=>{posted=JSON.parse(opts.body);return {ok:true}},readStream:async(_r,onChunk)=>{onChunk(boilerplate);return 'stop'}
};
vm.createContext(ctx);
vm.runInContext(src,ctx);
vm.runInContext(html.slice(html.indexOf('function toolFormats('),html.indexOf("if(globalThis.BoitiaTools){\n $('toolsbar')")),ctx);
vm.runInContext(html.slice(html.indexOf('function requestMessages('),html.indexOf('setInterval(()=>',html.indexOf('function requestMessages('))),ctx);
(async()=>{
 await elements.composer.onsubmit({preventDefault(){}});
 assert.equal(elements.error.textContent,'');
 assert(posted.messages.at(-1).content.includes('EXPORTACIÓN LOCAL ACTIVA'));
 assert.equal(c.messages[1].content,'# Recetario\nPollo al horno con papas y limón.');
 assert.deepEqual(JSON.parse(JSON.stringify(c.messages[1].formats)),['pdf']);
 assert.equal(c.messages[1].fileOnly,true);
 const pending=el('div');ctx.renderPdfDelivery(pending,c.messages[1],true);
 assert.equal(pending.children[0].text,'Preparando tu PDF…');
 assert(!JSON.stringify(pending).includes('Pollo al horno'));
 const delivery=el('div');ctx.renderPdfDelivery(delivery,c.messages[1],false);
 assert.equal(delivery.children[0].text,'Preparé el PDF «Recetario».');
 assert(!JSON.stringify(delivery).includes('Pollo al horno'));
 const file=delivery.children[1].children.find(x=>x.label==='↓ PDF');
 assert(file);file.fn();assert(downloads.at(-1).data.includes('Pollo al horno'));
 const partial=el('div');ctx.renderPdfDelivery(partial,{...c.messages[1],interrupted:true},false);
 assert(partial.children[1].children.some(x=>x.label==='↓ PDF parcial'));
 // The complete document remains local; unrelated future requests receive a short history entry.
 c.messages.push({role:'user',content:'Qué hora es?'});
 const compact=ctx.requestMessages(c,'Qué hora es?');
 assert(!compact[1].content.includes('Pollo al horno'));
 assert(compact[1].content.includes('Recetario'));
 c.messages[2].content='Corregí el PDF anterior';
 assert(ctx.requestMessages(c,'Corregí el PDF anterior')[1].content.includes('Pollo al horno'));
 c.messages.pop();
 downloads.length=0;
 // Exercise actual chat rendering, not only the delivery helper.
 ctx.safeBody=(text)=>el('div','body',text);
 vm.runInContext(html.slice(html.indexOf('function renderChat('),html.indexOf('let attachedFile=')),ctx);
 const view=el('div');ctx.renderChat(view);
 assert(!JSON.stringify(view).includes('Pollo al horno'));
 assert(JSON.stringify(view).includes('Preparé el PDF'));
 ctx.busy=true;
 const working=el('div');ctx.renderChat(working);
 assert(!JSON.stringify(working).includes('Pollo al horno'));assert(JSON.stringify(working).includes('Preparando tu PDF'));
 ctx.busy=false;
 const container=el('div');ctx.renderToolOutput(container,c.messages[1],c.messages[0]);
 const button=container.children[0].children.find(x=>x.label==='↓ PDF');
 assert(button);button.fn();assert.equal(downloads.length,1);assert(downloads[0].data.startsWith('%PDF-1.4'));
 const older=el('div');ctx.renderToolOutput(older,{role:'assistant',content:boilerplate},c.messages[0]);
 assert(older.children[0].children.some(x=>x.label==='↓ PDF'));
 const top=el('div');ctx.renderToolOutput(top,{role:'assistant',content:boilerplate},c.messages[0],'top');assert(top.children[0].children.some(x=>x.label==='↓ PDF'));
 const normal=el('div');ctx.renderToolOutput(normal,{role:'assistant',content:'Hola mundo'},{role:'user',content:'Hola'});
 assert.equal(normal.children[0].tag,'details');assert.equal(normal.children[0].children[0].text,'Descargar respuesta como archivo');
 console.log('PASS: actual submit, file-only chat and partial delivery, compact history, revision, local PDF download');
})().catch(e=>{console.error(e);process.exitCode=1});
