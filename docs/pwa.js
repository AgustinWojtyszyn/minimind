/* Install the public web app without altering inference or workspace storage. */
(function(){
 'use strict';
 const button=document.getElementById('installApp');
 if(!button)return;
 const standalone=window.matchMedia('(display-mode: standalone)');
 let pending=null, installed=false;
 function sync(){button.hidden=installed||standalone.matches||navigator.standalone===true||!window.isSecureContext;}
 window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();pending=event;sync();});
 window.addEventListener('appinstalled',()=>{installed=true;pending=null;sync();});
 if(standalone.addEventListener)standalone.addEventListener('change',sync);
 else if(standalone.addListener)standalone.addListener(sync);
 button.addEventListener('click',async()=>{
   if(pending){const event=pending;pending=null;button.disabled=true;
     try{await event.prompt();const choice=await event.userChoice;if(choice.outcome==='accepted'){installed=true;sync();}}
     catch{instructions();}finally{button.disabled=false;}
   }else instructions();
 });
 function instructions(){
   const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
   window.alert(ios?'En Safari, tocá Compartir y luego Agregar a inicio.':'Abrí el menú de tu navegador y elegí Instalar aplicación o Agregar a pantalla de inicio. Si no aparece, probá en Chrome o Edge.');
 }
 sync();
 if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('./sw.js').catch(()=>{});
})();
