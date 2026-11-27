const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
for(const path of ['frontend/index.html','docs/index.html']){
 const html=fs.readFileSync(path,'utf8'),ctx={uid:()=>String(Math.random())};vm.createContext(ctx);
 vm.runInContext(html.slice(html.indexOf('function conversationInstruction('),html.indexOf("$('composer').onsubmit=")),ctx);
 const state={memories:[{id:'old',text:'Dato anterior'}],lessons:[]};
 assert.match(ctx.conversationInstruction('Recordá que siempre prefiero respuestas cortas',state),/guardé/);
 assert.equal(state.memories[1].kind,'instruction');
 assert.equal(state.memories.length,2);
 ctx.conversationInstruction('Recordá que siempre prefiero respuestas cortas',state);assert.equal(state.memories.length,2);
 assert.match(ctx.conversationInstruction('¿Qué recordás de mí?',state),/Dato anterior/);
 assert.match(ctx.conversationInstruction('Mostrame mis recuerdos.',state),/respuestas cortas/);
 assert.match(ctx.conversationInstruction('Olvidá el recuerdo 1',state),/Quité/);assert.equal(state.memories.length,1);
 assert.match(ctx.conversationInstruction('Aprendé: Capital de Francia => París',state),/enseñanza/);assert.equal(state.lessons.length,1);
 assert.equal(ctx.conversationInstruction('Explicame la fotosíntesis',state),null);
 assert(!html.includes('data-view="memory"'));assert(!html.includes('data-view="learning"'));assert(!html.includes('data-view="lab"'));
 assert(!html.includes('Respaldo local opcional'));assert(html.includes('boitia.workspace.v1'));
}
console.log('PASS: chat memory, correction examples, duplicate protection, list/delete, simplified navigation');
