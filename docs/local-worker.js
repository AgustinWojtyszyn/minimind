// All model execution occurs in this worker, not an inference API.
import { pipeline, TextStreamer, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1';
env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends.onnx.wasm) env.backends.onnx.wasm.numThreads = 1;
let pipe, model, device, running=false;
const models={webgpu:'onnx-community/Qwen2.5-1.5B-Instruct',wasm:'onnx-community/Qwen2.5-0.5B-Instruct'};
async function load(){
    if(pipe)return;
    for(const candidate of (navigator.gpu?['webgpu','wasm']:['wasm'])){
        try{
            postMessage({type:'progress',message:'Preparando '+models[candidate]+' ('+candidate+')…'});
            pipe=await pipeline('text-generation',models[candidate],{
                device:candidate,dtype:'q4',progress_callback:p=>{
                    if(p.status==='progress')postMessage({type:'progress',message:'Descargando '+p.file+' · '+Math.round(p.progress||0)+'%'});
                }
            });
            model=models[candidate];device=candidate;return;
        }catch(err){
            pipe=null;
            if(candidate==='wasm')throw err;
            postMessage({type:'progress',message:'WebGPU no disponible. Intentando el modelo CPU reducido…'});
        }
    }
}
self.onmessage=async({data})=>{
    if(running){postMessage({type:'error',message:'El motor local está ocupado.'});return}
    running=true;
    try{
        await load();
        if(data.type==='init'){postMessage({type:'ready',model,device});return}
        if(data.type!=='generate')throw Error('Operación inválida');
        const max=Math.min(device==='wasm'?256:768,Math.max(1,data.maxTokens||256));
        const items=data.messages.map(({role,content})=>({role,content}));
        const encode=()=>pipe.tokenizer.apply_chat_template(items,{add_generation_prompt:true,tokenize:true,return_tensor:false});
        while(encode().length>2048-max&&items.length>2){
            items.splice(1,items[1]?.role==='user'&&items[2]?.role==='assistant'?2:1);
        }
        if(encode().length>2048-max)throw Error('La consulta supera el contexto del modelo local.');
        let text='';
        const streamer=new TextStreamer(pipe.tokenizer,{skip_prompt:true,skip_special_tokens:true,callback_function:chunk=>{
            text+=chunk;postMessage({type:'chunk',text});
        }});
        await pipe(items,{max_new_tokens:max,do_sample:false,return_full_text:false,streamer});
        if(!text.trim())throw Error('El motor local devolvió una respuesta vacía.');
        // Token accounting is best-effort here; do not claim exact timing/usage.
        postMessage({type:'done',text:text.trim(),finish_reason:'unknown'});
    }catch(err){postMessage({type:'error',message:String(err?.message||err).slice(0,250)})}
    finally{running=false}
};
