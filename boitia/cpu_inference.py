"""CPU-only adapter for the same safe BoitIA API, using a local open-weight GGUF."""
import time
from .inference import Result, adaptive_budget


class CPUResponder:
    def __init__(self,llm):
        self.llm=llm

    def __call__(self,messages,mode,max_tokens,temperature,*,on_text=None,cancel=None):
        max_new=min(256,adaptive_budget(messages,mode,max_tokens))
        items=[dict(m) for m in messages]
        # ChatML framing overhead is reserved explicitly, in addition to output budget.
        def count():
            return sum(len(self.llm.tokenize(m["content"].encode(),add_bos=False)) + 12 for m in items)
        while len(items)>2 and count()>4096-max_new-32:
            remove=2 if len(items)>3 and items[1]["role"]=="user" and items[2]["role"]=="assistant" else 1
            del items[1:1+remove]
        if count()>4096-max_new-32:
            raise ValueError("Tu consulta supera el contexto del motor CPU.")
        start=time.perf_counter()
        first=None
        text=""
        finish=None
        stream=self.llm.create_chat_completion(messages=items,max_tokens=max_new,
                                               temperature=temperature,stream=True)
        try:
            for chunk in stream:
                if cancel is not None and cancel.is_set():
                    raise RuntimeError("Consulta cancelada")
                choice=chunk["choices"][0]
                delta=choice.get("delta",{}).get("content") or ""
                if delta:
                    if first is None:first=time.perf_counter()-start
                    text+=delta
                    if on_text:on_text(delta)
                if choice.get("finish_reason"):finish=choice["finish_reason"]
        finally:
            stream.close()
        if not text.strip():raise RuntimeError("Respuesta neuronal vacía")
        # Counts from tokenizer are estimates of visible tokens, not exact engine usage.
        return Result(text.strip(),count(),len(self.llm.tokenize(text.encode(),add_bos=False)),
                      time.perf_counter()-start,finish or "stop",None,first)
