const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert/strict');
class Node{
  constructor(tag,text=''){this.tag=tag;this.value=text;this.children=[]}
  append(...nodes){this.children.push(...nodes)}
  get text(){return this.value+this.children.map(x=>x.text).join('')}
  all(tag){return [...(this.tag===tag?[this]:[]),...this.children.flatMap(x=>x.all(tag))]}
}
const el=(tag,cls,txt)=>new Node(tag,txt||''),document={createTextNode:t=>new Node('#text',t)};
for(const file of ['frontend/index.html','docs/index.html']){
 const html=readFileSync(file,'utf8'),ctx=vm.createContext({el,document,URL});
 for(const s of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(s[1]);
 const start=html.indexOf('function renderInline('),end=html.indexOf('function importBackup(',start);
 vm.runInContext(html.slice(start,end),ctx);
 const render=ctx.safeBody;
 const n=render('### **1. Título**\n\nTexto **negrita** y *cursiva* 😊.\n\n---\n- Uno\n  - Dos\n\n3. Tres\n4. Cuatro\n\n> Cita\n\n| A | B |\n|---|---|\n| x | y |\n\n'+'~~~js\n<script>alert(1)</script>\n~~~\n\n[web](https://example.com) [mal](javascript:alert(1)) <img src=x onerror=alert(1)>');
 assert.equal(n.all('h4')[0].text,'1. Título');
 assert.equal(n.all('strong').length,2);assert.equal(n.all('em')[0].text,'cursiva');
 assert.equal(n.all('hr').length,1);assert.equal(n.all('ul').length,2);
 assert.equal(n.all('ol')[0].start,3);assert.equal(n.all('li').length,4);
 assert.equal(n.all('blockquote')[0].text,'Cita');
 assert.equal(n.all('th').length,2);assert.equal(n.all('td').length,2);
 assert.equal(n.all('pre')[0].text,'<script>alert(1)</script>');
 assert.equal(n.all('a').length,1);assert.equal(n.all('a')[0].rel,'noopener noreferrer');
 assert.equal(n.all('img').length,0);assert.equal(n.all('script').length,0);
 assert(n.text.includes('javascript:alert(1)'));assert(n.text.includes('😊'));
 assert.equal(render('**pendiente').text,'**pendiente');
 assert.equal(render('~~~python\nprint(1)').all('pre')[0].text,'print(1)');
 assert.equal(render('**literal**',false).text,'**literal**');
 assert.equal(render('**A**\r\n**B**').all('strong').length,2);
}
console.log('PASS: both frontends, Markdown blocks/inlines, partial output, safe links and literal HTML');
