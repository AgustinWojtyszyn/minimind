/* Network-first navigation only. Never cache API requests, chat data or engine.json. */
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 const request=event.request;
 if(request.method!=='GET'||request.mode!=='navigate'||!request.url.startsWith(self.registration.scope))return;
 event.respondWith(fetch(request).catch(()=>new Response('<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Boiti</title><body style="background:#101113;color:#eef1ef;font:18px system-ui;padding:24px"><h1>Boiti</h1><p>Sin conexión. Volvé a conectarte y recargá la aplicación.</p><a style="color:#b5f0d0" href="./">Reintentar</a></body></html>',{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})));
});
