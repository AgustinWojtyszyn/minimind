// Thin worker controller, lazy download only after user approval.
(function(){
    'use strict';
    let worker=null,pending=null,ready=null;
    const root=new URL('.',document.currentScript.src);
    function request(data,onProgress,onChunk,timeout){
        if(pending)return Promise.reject(Error('El motor local está ocupado.'));
        if(!worker){
            worker=new Worker(new URL('local-worker.js',root),{type:'module'});
            worker.onerror=()=>{const p=pending;reset();p?.reject(Error('No se pudo cargar el motor local.'));};
            worker.onmessage=({data:m})=>{
                if(!pending)return;
                if(m.type==='progress'){pending.onProgress?.(m.message);return}
                if(m.type==='chunk'){pending.onChunk?.(m.text);return}
                const p=pending;pending=null;clearTimeout(p.timer);
                if(m.type==='error'){p.reject(Error(m.message));return}
                if(m.type==='ready')ready=m;
                p.resolve(m);
            };
        }
        return new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>{reset();reject(Error('El motor local agotó el tiempo de espera.'));},timeout);
            pending={resolve,reject,onProgress,onChunk,timer};
            worker.postMessage(data);
        });
    }
    function reset(){if(pending)clearTimeout(pending.timer);pending=null;ready=null;worker?.terminate();worker=null}
    window.BoitiaPortable={
        async init(onProgress){return ready||request({type:'init'},onProgress,null,900000)},
        generate(messages,maxTokens,onChunk){return request({type:'generate',messages,maxTokens},null,onChunk,600000)},
        reset
    };
})();
