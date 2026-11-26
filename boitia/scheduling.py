"""Exact bounded scheduling reference for offline evaluation. No arbitrary code execution."""
from itertools import permutations

def solve(tasks, precedences, deadlines):
    if not isinstance(tasks, dict) or not 1 <= len(tasks) <= 8:
        raise ValueError('Se admiten de 1 a 8 tareas.')
    if any(not isinstance(v,(tuple,list)) or len(v)!=2 or any(type(x) is not int or not 1<=x<=10000 for x in v) for v in tasks.values()):
        raise ValueError('Duraciones y prioridades enteras positivas.')
    if any(a not in tasks or b not in tasks or a==b for a,b in precedences) or any(k not in tasks or type(v) is not int or v<0 for k,v in deadlines.items()):
        raise ValueError('Restricciones inválidas.')
    valid = 0; best = None; orders = []
    for order in permutations(tasks):
        pos = {k:i for i,k in enumerate(order)}
        if any(pos[a]>=pos[b] for a,b in precedences): continue
        elapsed = cost = 0; feasible = True
        for k in order:
            d,w = tasks[k]; elapsed += d; cost += elapsed*w
            if k in deadlines and elapsed > deadlines[k]: feasible=False; break
        if not feasible: continue
        valid += 1
        if best is None or cost < best: best=cost; orders=[order]
        elif cost==best: orders.append(order)
    return {'valid':valid, 'cost':best, 'orders':orders}
