"""Bounded generation with truthful accounting and adaptive budgets."""
import time
from dataclasses import dataclass
from .config import PROFILES

@dataclass
class Result:
    text: str
    input_tokens: int
    output_tokens: int
    elapsed: float
    finish_reason: str


def generate(model, tokenizer, messages, mode='balanced', max_tokens=None, temperature=None, *, on_text=None, cancel=None):
    import torch
    profile = PROFILES[mode]
    max_new = profile.output if max_tokens is None else min(profile.output, max(1, max_tokens))
    temp = profile.temperature if temperature is None else temperature
    options = {'tokenize':False, 'add_generation_prompt':True}
    if getattr(model.config, 'model_type', '') == 'qwen3':
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
    if on_text is not None:
        from transformers import TextStreamer
        class CallbackStreamer(TextStreamer):
            def on_finalized_text(self, text, stream_end=False):
                if text:
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
    if not answer:
        raise RuntimeError('Respuesta neuronal vacía')
    return Result(answer, n, len(tokens), time.perf_counter()-start, 'length' if len(tokens)>=max_new else 'stop')


def respond(model, tokenizer, messages, mode='balanced', max_tokens=None, temperature=None, *, on_text=None, cancel=None):
    """Deep mode: a bounded draft followed by a separate verification/revision generation.

    Only the revised answer is returned, with both passes accounted for in metrics.
    """
    if mode != 'deep':
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
        final = generate(model, tokenizer, messages, mode, total, temperature, on_text=on_text, cancel=cancel)
    else:
        final = generate(model, tokenizer, review, mode, total, temperature, on_text=on_text, cancel=cancel)
    final.elapsed += draft.elapsed
    # OpenAI usage describes both passes, not solely user-visible output.
    final.input_tokens += draft.input_tokens
    final.output_tokens += draft.output_tokens
    return final
