"""Safe expression evaluation for subgraph IR bindings and edge conditions.

Supports:
- {{path.to.value}} interpolation inside strings
- Comparisons and boolean ops for `when` clauses
- JSONPath-lite dotted paths with [index]

Does NOT execute arbitrary Python.
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any


_INTERP = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_PATH_TOKEN = re.compile(r"([a-zA-Z_][\w]*)|\[(\d+)\]")

_BIN_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_UNARY_OPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
}


def resolve_path(context: dict[str, Any], path: str) -> Any:
    """Resolve dotted/indexed path against context."""
    path = path.strip()
    if not path:
        return None
    cur: Any = context
    # Support a.b[0].c
    parts: list[str | int] = []
    buf = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
            i += 1
            continue
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = path.index("]", i)
            parts.append(int(path[i + 1 : j]))
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        parts.append(buf)

    for part in parts:
        if cur is None:
            return None
        if isinstance(part, int):
            if not isinstance(cur, (list, tuple)) or part >= len(cur):
                return None
            cur = cur[part]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def interpolate(template: str, context: dict[str, Any]) -> str:
    """Replace {{paths}} in a string template."""

    def repl(match: re.Match[str]) -> str:
        val = resolve_path(context, match.group(1))
        return "" if val is None else str(val)

    return _INTERP.sub(repl, template)


def bind_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Deep-bind param values; strings with {{}} are interpolated; bare {{path}} becomes raw value."""

    def bind_value(value: Any) -> Any:
        if isinstance(value, str):
            full = _INTERP.fullmatch(value.strip())
            if full:
                return resolve_path(context, full.group(1))
            if "{{" in value:
                return interpolate(value, context)
            return value
        if isinstance(value, dict):
            return {k: bind_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [bind_value(v) for v in value]
        return value

    return {k: bind_value(v) for k, v in params.items()}


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return resolve_path(context, node.id)
    if isinstance(node, ast.Attribute):
        base = _eval_node(node.value, context)
        if isinstance(base, dict):
            return base.get(node.attr)
        return getattr(base, node.attr, None)
    if isinstance(node, ast.Subscript):
        base = _eval_node(node.value, context)
        sl = node.slice
        if isinstance(sl, ast.Constant):
            key = sl.value
        else:
            key = _eval_node(sl, context)
        if isinstance(base, dict):
            return base.get(key)
        if isinstance(base, (list, tuple)) and isinstance(key, int):
            return base[key] if key < len(base) else None
        return None
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, context))
    if isinstance(node, ast.BoolOp):
        op = _BIN_OPS[type(node.op)]
        values = [_eval_node(v, context) for v in node.values]
        cur = values[0]
        for nxt in values[1:]:
            cur = op(cur, nxt)
        return cur
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            fn = _BIN_OPS.get(type(op))
            if fn is None or not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](
            _eval_node(node.left, context),
            _eval_node(node.right, context),
        )
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def evaluate(expr: str, context: dict[str, Any]) -> Any:
    """Evaluate a boolean/arithmetic expression against context.

    Name references resolve as top-level context keys (and dotted attrs).
    For nested paths in comparisons, prefer interpolating into values first,
    or use names that exist at the top level of context.
    """
    expr = expr.strip()
    if not expr:
        return True
    # Allow {{path}} as a whole expression meaning truthiness of resolved value
    full = _INTERP.fullmatch(expr)
    if full:
        return resolve_path(context, full.group(1))
    # Rewrite {{a.b}} inside expression to a dotted Name chain via string replace of quotes
    # Simpler approach: replace {{path}} with a synthetic lookup using resolve in Compare via Names
    # Convert {{foo.bar}} → __path__('foo.bar')
    rewritten = _INTERP.sub(lambda m: f"__path__({m.group(1)!r})", expr)

    tree = ast.parse(rewritten, mode="eval")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "__path__":
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
                raise ValueError("Invalid __path__ call")
            return resolve_path(context, str(node.args[0].value))
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return resolve_path(context, node.id)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BoolOp):
            op = _BIN_OPS[type(node.op)]
            values = [_eval(v) for v in node.values]
            cur = values[0]
            for nxt in values[1:]:
                cur = op(cur, nxt)
            return cur
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval(comparator)
                fn = _BIN_OPS.get(type(op))
                if fn is None or not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return _eval(tree)
