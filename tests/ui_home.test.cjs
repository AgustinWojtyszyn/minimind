const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('frontend/index.html','utf8');
const docs=fs.readFileSync('docs/index.html','utf8');
const el=(tag,cls,text)=>({tag,cls,text,children:[],append(...xs){this.children.push(...xs)}});
let destination='',focused=false;const prompt={value:'',focus(){focused=true}};
const ctx={chat:()=>null,el,btn:(label,fn,cls)=>({label,fn,cls,children:[],append(...xs){this.children.push(...xs)}}),logo:'<svg></svg>',portable:false,connected:true,$:()=>prompt,show:p=>{destination=p}};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function renderChat('),html.indexOf('let attachedFile=')),ctx);
const view=el('div');ctx.renderChat(view);
const hero=view.children[0].children[0],grid=hero.children.find(x=>x.cls==='suggestions');
assert.equal(hero.children.find(x=>x.tag==='h1').text,'Una mente en evolución.');
assert.deepEqual(grid.children.map(x=>x.label),['Explorar una idea','Resolver un problema','Enseñar a Boiti','Revisar recuerdos']);
for(const card of grid.children){card.fn();const first=prompt.value;assert(focused&&first.length>10);card.fn();assert.notEqual(prompt.value,first);assert.equal(destination,'');}
assert(html.includes('.suggestions{grid-template-columns:repeat(2,minmax(0,1fr))'));
assert(html.includes('--bg:#101113'));assert(!html.includes('--bg:#101613'));
assert(html.includes('class="boiti-tech-icon"'));assert(html.includes('data:image/png;base64,'));assert(!html.includes('<ellipse cx="24" cy="24"'));assert(docs.includes('class="boiti-tech-icon"'));
assert(docs.includes('interfaz v6'));assert(docs.includes('tools.js?v=5'));
console.log('PASS: original quadrants, actions, neutral theme, Boiti Tech logo, delivered tools retained');
