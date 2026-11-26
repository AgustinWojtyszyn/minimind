"""Relevant local memories are selected by client; server treats them as untrusted data."""
import re

def words(text):
    return {w for w in re.findall(r'\w+', text.casefold()) if len(w)>2}

def select_memories(query, memories, limit=5):
    q=words(query)
    ranked=[]
    for m in memories[:200]:
        if not isinstance(m,str): continue
        score=len(q & words(m))
        if score: ranked.append((score,m[:600]))
    return [m for _,m in sorted(ranked, key=lambda item:item[0], reverse=True)[:limit]]
