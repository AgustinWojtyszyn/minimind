const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
for(const file of ['frontend/index.html','docs/index.html']){
 const html=readFileSync(file,'utf8');
 const boot=html.slice(html.lastIndexOf("active=null;persist();show('chat');"),html.lastIndexOf('</script>')).trim();
 assert.ok(boot.startsWith('active=null;'),file);
 const state={chats:[{id:'old',messages:[{role:'user',content:'Hola'}]}],memories:[{text:'recuerdo'}],lessons:[{question:'q',answer:'a'}]};
 const before=JSON.stringify(state);
 let page=null,connects=0;
 const ctx={state,active:'old',persist:()=>{},show:p=>page=p,connectPublic:()=>connects++};
 vm.createContext(ctx);vm.runInContext(boot,ctx);
 assert.equal(ctx.active,null);assert.equal(page,'chat');assert.equal(connects,1);
 assert.equal(JSON.stringify(state),before,'Startup must not mutate historical data');
 assert.ok(html.includes("active=c.id;show('chat')"),'History remains selectable');
}
console.log('PASS: both frontends open a fresh conversation without losing saved history or memory');
