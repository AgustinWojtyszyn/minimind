"""Bounded arithmetic interpreter. No eval, imports, variables or attribute access."""
import ast
import operator
from fractions import Fraction

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}

def calculate(expression):
    if not isinstance(expression,str) or len(expression)>256: raise ValueError('Expresión demasiado larga.')
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>64: raise ValueError('Demasiadas operaciones.')
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):
            value=Fraction(str(n.value))
        elif isinstance(n,ast.UnaryOp) and type(n.op) in (ast.UAdd,ast.USub):
            value=visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        elif isinstance(n,ast.BinOp) and type(n.op) in OPS:
            value=OPS[type(n.op)](visit(n.left),visit(n.right))
        else: raise ValueError('Operación no permitida.')
        if value.numerator.bit_length()>1024 or value.denominator.bit_length()>1024: raise ValueError('Resultado demasiado grande.')
        return value
    return str(visit(tree.body))
