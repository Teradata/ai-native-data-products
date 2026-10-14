"""Parse the Design Specification Standard's expression vocabulary, and render it.

A specification writes derivations, measures and conditions in a closed, platform-neutral
vocabulary (Design Specification Standard §5). This module turns that text into a tree,
and renders a tree as SQL using the fragments a platform binding declares in its
`Functions:` block (Platform Implementation Authoring Standard §5.1). No SQL lives here:
every function, literal and duration is rendered from the binding's declaration, and
operators are written as the vocabulary writes them. A function the binding does not
declare makes the expression unrenderable for that binding, which is reported, never
approximated.

Stdlib only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<number>\d+(?:\.\d+)?|\.\d+)
  | (?P<string>'(?:[^']|'')*')
  | (?P<op><>|<=|>=|=|<|>|\+|-|\*|/)
  | (?P<punct>[(),{}:.])
  | (?P<word>[A-Za-z_][A-Za-z0-9_\-]*)
""", re.X)

DURATION_UNITS = ("hour", "day", "week", "month", "year")
COMPARISON = ("=", "<>", "<", "<=", ">", ">=")


class ExpressionError(ValueError):
    pass


@dataclass
class Node:
    kind: str  # number, string, bool, null, duration, ref, call, map, unary, binary
    value: object = None
    args: List["Node"] = field(default_factory=list)
    pairs: List[Tuple[str, "Node"]] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {"kind": self.kind}
        if self.value is not None:
            out["value"] = self.value
        if self.args:
            out["args"] = [a.to_dict() for a in self.args]
        if self.pairs:
            out["pairs"] = [[k, v.to_dict()] for k, v in self.pairs]
        return out


def tokenize(text: str) -> List[Tuple[str, str]]:
    out, i = [], 0
    while i < len(text):
        m = TOKEN.match(text, i)
        if not m:
            raise ExpressionError(f"unexpected character {text[i]!r} at {i}")
        if m.lastgroup != "ws":
            out.append((m.lastgroup, m.group()))
        i = m.end()
    return out


class Parser:
    """Precedence: or < and < not < comparison < additive < multiplicative < unary."""

    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.i = 0

    def peek(self, offset=0):
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if tok[0] is None or (value is not None and tok[1].lower() != value):
            raise ExpressionError(f"expected {value or 'a token'}, found {tok[1]!r}")
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.or_()
        if self.peek()[0] is not None:
            raise ExpressionError(f"unexpected {self.peek()[1]!r}")
        return node

    def or_(self):
        node = self.and_()
        while self.peek()[1] and self.peek()[1].lower() == "or":
            self.take()
            node = Node("binary", "or", [node, self.and_()])
        return node

    def and_(self):
        node = self.not_()
        while self.peek()[1] and self.peek()[1].lower() == "and":
            self.take()
            node = Node("binary", "and", [node, self.not_()])
        return node

    def not_(self):
        if self.peek()[1] and self.peek()[1].lower() == "not" and self.peek(1)[1] != "(":
            self.take()
            return Node("unary", "not", [self.not_()])
        return self.comparison()

    def comparison(self):
        node = self.additive()
        if self.peek()[1] in COMPARISON:
            op = self.take()[1]
            node = Node("binary", op, [node, self.additive()])
        return node

    def additive(self):
        node = self.multiplicative()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            node = Node("binary", op, [node, self.multiplicative()])
        return node

    def multiplicative(self):
        node = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            node = Node("binary", op, [node, self.unary()])
        return node

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            return Node("unary", "-", [self.unary()])
        return self.primary()

    def primary(self):
        kind, value = self.peek()
        if kind == "number":
            self.take()
            nxt = self.peek()[1]
            unit = nxt.lower().rstrip("s") if nxt else None
            if unit in DURATION_UNITS and self.peek()[0] == "word":
                self.take()
                return Node("duration", {"n": value, "unit": unit})
            return Node("number", value)
        if kind == "string":
            self.take()
            return Node("string", value[1:-1].replace("''", "'"))
        if value == "(":
            self.take()
            node = self.or_()
            self.take(")")
            return node
        if value == "{":
            return self.map_literal()
        if kind == "word":
            low = value.lower()
            if low in ("true", "false"):
                self.take()
                return Node("bool", low)
            if low == "null":
                self.take()
                return Node("null")
            self.take()
            if self.peek()[1] == "(":
                self.take()
                args = []
                if self.peek()[1] != ")":
                    args.append(self.or_() if self.peek()[1] != "{" else self.map_literal())
                    while self.peek()[1] == ",":
                        self.take()
                        args.append(self.or_() if self.peek()[1] != "{" else self.map_literal())
                self.take(")")
                return Node("call", low, args)
            if self.peek()[1] == ".":
                self.take()
                attr = self.take()[1]
                return Node("ref", {"entity": value, "attribute": attr})
            return Node("ref", {"entity": value, "attribute": None})
        raise ExpressionError(f"unexpected {value!r}")

    def map_literal(self):
        self.take("{")
        pairs = []
        while self.peek()[1] != "}":
            kind, key = self.take()
            if kind == "string":
                key = key[1:-1].replace("''", "'")
            while self.peek()[1] not in (":",):  # bare keys may span tokens: CAT-006, Service Desk
                key += self.take()[1]
            self.take(":")
            pairs.append((key, self.or_()))
            if self.peek()[1] == ",":
                self.take()
        self.take("}")
        return Node("map", pairs=pairs)


def parse(text: str) -> Node:
    return Parser(text).parse()


def references(node: Node) -> List[Tuple[str, Optional[str]]]:
    """Every `(entity, attribute)` the expression reads, in order, without repeats."""
    out = []

    def walk(n: Node):
        if n.kind == "ref" and (n.value["entity"], n.value["attribute"]) not in out:
            out.append((n.value["entity"], n.value["attribute"]))
        for a in n.args:
            walk(a)
        for _, v in n.pairs:
            walk(v)
    walk(node)
    return out


def functions_used(node: Node) -> List[str]:
    out = []

    def walk(n: Node):
        if n.kind == "call" and n.value not in out:
            out.append(n.value)
        for a in n.args:
            walk(a)
        for _, v in n.pairs:
            walk(v)
    walk(node)
    return out


class Unrenderable(ValueError):
    """The binding declares no fragment for something the expression uses."""


# Argument positions that are conditions, by function: a Flag there is a truth value.
CONDITION_ARGS = {"when": (0,), "as_flag": (0,), "validity": (0,), "consistency": (0,),
                  "completeness": (1,)}


def render(node: Node, functions: Dict[str, str], ref: Callable[[str, Optional[str]], str],
           literal: Callable[[str], str], is_flag: Callable[[str, Optional[str]], bool] = None,
           condition: bool = False) -> str:
    """SQL for `node`, using the binding's `functions` fragments.

    `ref(entity, attribute)` renders an attribute reference, or an entity argument when
    `attribute` is None; `literal(text)` quotes a text literal. Where a `Flag` stands as a
    condition and the binding declares a `flag test` fragment, the reference is wrapped in
    it: a platform without a boolean type tests the flag's value. `condition` says whether
    `node` itself is in a condition position (a filter, a `Where`).
    """
    def fragment(name: str, arity: int) -> str:
        for key in (f"{name}/{arity}", name):
            if key in functions:
                return functions[key]
        raise Unrenderable(name)

    def fill(template: str, args: List[str], **extra) -> str:
        out = template.replace("{args}", ", ".join(args))
        for k, v in extra.items():
            out = out.replace("{" + k + "}", v)
        return re.sub(r"\{(\d+)\}", lambda m: args[int(m.group(1))], out)

    def r(n: Node, cond: bool = False) -> str:
        if (cond and n.kind == "ref" and "flag test" in functions and is_flag
                and is_flag(n.value["entity"], n.value["attribute"])):
            return fill(functions["flag test"], [ref(n.value["entity"], n.value["attribute"])])
        if n.kind == "number":
            return str(n.value)
        if n.kind == "string":
            return literal(n.value)
        if n.kind in ("bool", "null"):
            return fragment(n.value if n.kind == "bool" else "null", 0)
        if n.kind == "duration":
            return fill(fragment("duration", 0), [], n=n.value["n"], unit=n.value["unit"])
        if n.kind == "ref":
            return ref(n.value["entity"], n.value["attribute"])
        if n.kind == "unary":
            inner = r(n.args[0], n.value == "not")
            return f"NOT ({inner})" if n.value == "not" else f"-({inner})"
        if n.kind == "binary":
            logical = n.value in ("and", "or")
            op = n.value.upper() if logical else n.value
            return f"({r(n.args[0], logical)} {op} {r(n.args[1], logical)})"
        if n.kind == "call":
            if n.value == "map":
                subject, table = n.args[0], n.args[1]
                case = fragment("map case", 0)
                pairs = " ".join(fill(case, [], key=literal(k), value=r(v)) for k, v in table.pairs)
                return fill(fragment("map", 2), [r(subject)], cases=pairs)
            positions = CONDITION_ARGS.get(n.value, ())
            args = [r(a, i in positions) for i, a in enumerate(n.args)]
            return fill(fragment(n.value, len(args)), args)
        if n.kind == "map":
            raise Unrenderable("a map literal outside map()")
        raise Unrenderable(n.kind)
    return r(node, condition)
