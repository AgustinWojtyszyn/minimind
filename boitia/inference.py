"""Bounded generation with truthful accounting and adaptive budgets."""
import time
import os
import re
from dataclasses import dataclass
from .config import PROFILES

@dataclass
class Result:
    text: str
    input_tokens: int
    output_tokens: int
    elapsed: float
    finish_reason: str
    ttft_seconds: float | None = None
    first_visible_seconds: float | None = None


def adaptive_budget(messages, mode, requested=None):
    """Only shorten obviously brief requests; explicit explanations retain full budget."""
    ceiling = PROFILES[mode].output
    limit = ceiling if requested is None else min(ceiling, max(1, requested))
    query = messages[-1]["content"].strip().casefold()
    if mode != "deep" and re.fullmatch(r"(hola|buen[oa]s? (días|tardes|noches)|gracias|hello|hi)[.!¡! ]*", query):
        return min(limit, 64)
    if mode != 'deep' and len(query) < 600 and re.search(r"(solo|únicamente|exclusivamente) (el entero|un entero|sí o no|el número|un número)[.! ]*$", query):
        return min(limit, 64)
    return limit


def generate(model, tokenizer, messages, mode='balanced', max_tokens=None, temperature=None, *, on_text=None, cancel=None):
    import torch
    profile = PROFILES[mode]
    max_new = adaptive_budget(messages, mode, max_tokens)
    temp = profile.temperature if temperature is None else temperature
    options = {'tokenize':False, 'add_generation_prompt':True}
    if getattr(model.config, 'model_type', '') in ('qwen3', 'qwen3_moe'):
        options['enable_thinking'] = False  # concise public answers; never expose internal reasoning traces
    def encode(items):
        text = tokenizer.apply_chat_template(items, **options)
        return tokenizer(text, return_tensors='pt', return_token_type_ids=False, add_special_tokens=False)
    limit = min(profile.context, int(getattr(model.config, 'max_position_embeddings', 32768))) - max_new
    if limit < 64:
        raise ValueError('Presupuesto de contexto insuficiente.')
    items = list(messages)
    encoded = encode(items)
    # Remove old complete turns rather than truncate latest user request or system identity.
    while encoded['input_ids'].shape[-1] > limit and len(items) > 2:
        remove = 2 if len(items) > 3 and items[1]['role'] == 'user' and items[2]['role'] == 'assistant' else 1
        del items[1:1+remove]
        encoded = encode(items)
    n = encoded['input_ids'].shape[-1]
    if n > limit:
        raise ValueError('Tu última consulta supera el contexto disponible para este modo.')
    device = model.get_input_embeddings().weight.device
    inputs = {k:v.to(device) for k,v in encoded.items() if k in ('input_ids','attention_mask')}
    kwargs = dict(max_new_tokens=max_new, do_sample=temp > 0, use_cache=True,
                  pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    if temp > 0:
        kwargs.update(temperature=temp, top_p=0.9)
    from transformers import TextStreamer
    timing = {'token': None, 'visible': None}
    class CallbackStreamer(TextStreamer):
        def put(self, value):
            if not self.next_tokens_are_prompt and timing['token'] is None:
                timing['token'] = time.perf_counter() - start
            super().put(value)
        def on_finalized_text(self, text, stream_end=False):
            if text:
                if timing['visible'] is None:
                    timing['visible'] = time.perf_counter() - start
                if on_text is not None:
                    on_text(text)
    kwargs['streamer'] = CallbackStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    if cancel is not None:
        from transformers import StoppingCriteria, StoppingCriteriaList
        class CancelCriteria(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return torch.full((input_ids.shape[0],), cancel.is_set(), dtype=torch.bool, device=input_ids.device)
        kwargs['stopping_criteria'] = StoppingCriteriaList([CancelCriteria()])
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, **kwargs)
    tokens = output[0,n:]
    answer = tokenizer.decode(tokens, skip_special_tokens=True).strip()
    if cancel is not None and cancel.is_set():
        raise RuntimeError("Consulta cancelada")
    if not answer:
        raise RuntimeError('Respuesta neuronal vacía')
    return Result(answer, n, len(tokens), time.perf_counter()-start, 'length' if len(tokens)>=max_new else 'stop', timing['token'], timing['visible'])


def respond(model, tokenizer, messages, mode='balanced', max_tokens=None, temperature=None, *, on_text=None, cancel=None):
    """Single streaming pass by default; optional legacy two-pass review for comparison."""
    if mode == 'deep':
        messages = [dict(m) for m in messages]
        if messages[0]['role'] == 'system':
            messages[0]['content'] += '\nVerifica restricciones y cálculos. Entrega una justificación verificable cuando corresponda, respetando el formato solicitado.'
    if mode != 'deep' or os.environ.get("BOITIA_LEGACY_REVIEW") != "1":
        return generate(model, tokenizer, messages, mode, max_tokens, temperature, on_text=on_text, cancel=cancel)
    total = PROFILES[mode].output if max_tokens is None else max_tokens
    if total < 256:
        return generate(model, tokenizer, messages, mode, max_tokens, temperature, on_text=on_text, cancel=cancel)
    draft_budget = min(768, total // 3)
    draft = generate(model, tokenizer, messages, mode, draft_budget, temperature, cancel=cancel)
    if cancel is not None and cancel.is_set():
        raise RuntimeError("Consulta cancelada")
    review = list(messages) + [{'role':'assistant','content':draft.text},
        {'role':'user','content':'Revisa la respuesta provisional anterior contra mi solicitud original. Corrige los errores o restricciones incumplidas y entrega únicamente la respuesta final; no describas un razonamiento privado.'}]
    # Do not silently discard the original request when revising a long input.
    if draft.input_tokens + draft.output_tokens + 256 + total > PROFILES[mode].context:
        final = generate(model, tokenizer, messages, mode, total-draft_budget, temperature, on_text=on_text, cancel=cancel)
    else:
        final = generate(model, tokenizer, review, mode, total-draft_budget, temperature, on_text=on_text, cancel=cancel)
    final.elapsed += draft.elapsed
    if final.ttft_seconds is not None: final.ttft_seconds += draft.elapsed
    if final.first_visible_seconds is not None: final.first_visible_seconds += draft.elapsed
    # OpenAI usage describes both passes, not solely user-visible output.
    final.input_tokens += draft.input_tokens
    final.output_tokens += draft.output_tokens
    return final
