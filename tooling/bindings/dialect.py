"""The platform-neutral half of code generation: a dialect's base class and its loader.

A binding generates SQL through a dialect: `implementation/portable/dialect.py` holds the
portable defaults, and each `implementation/{platform}/dialect.py` subclasses them and
overrides what its platform does differently. Every method takes values from the build
context and returns SQL text: it reads no file, clock or environment, so generation is a
pure function of the context. This module holds no SQL; it loads the dialects and gives them
the context and the binding's quoting.

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IMPLEMENTATION = REPO / "implementation"
PORTABLE = "portable_dialect"


def _load(name: str, path: Path):
    """Import a dialect module. Loading writes nothing: no bytecode cache lands beside the
    dialect, inside the skill."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


def dialect_class(platform: str):
    """The dialect a platform generates with: `DIALECT` in its `dialect.py`."""
    path = IMPLEMENTATION / platform / "dialect.py"
    if not path.is_file():
        raise FileNotFoundError(f"the {platform} binding has no dialect.py")
    _load(PORTABLE, IMPLEMENTATION / "portable" / "dialect.py")
    return _load(f"{platform}_dialect", path).DIALECT


class Dialect:
    """What every dialect is given: the binding's declarations and the build context, with
    the quoting the binding declares. Nothing here composes a name or writes SQL."""

    def __init__(self, binding, context):
        self.binding = binding
        self.ctx = context
        self._by_name = {x["name"]: x for x in context["entities"] + context["relations"]}

    # ---- quoting ------------------------------------------------------------------------
    def ident(self, name) -> str:
        return self.binding.ident(name)

    def literal(self, value) -> str:
        return "NULL" if value is None else self.binding.literal(value)

    def qualified(self, obj) -> str:
        return self.binding.qualified(obj["container"], obj["name"])

    def cols(self, names) -> str:
        return ", ".join(self.ident(n) for n in names)

    # ---- the context ----------------------------------------------------------------------
    def relations(self):
        """Every entity and standard-owned relation, entities first."""
        return self.ctx["entities"] + self.ctx["relations"]

    def named(self, name):
        return self._by_name.get(name)

    def tables(self):
        """The relations this build creates a table for: defined, not adopted."""
        return [x for x in self.relations()
                if x["relation"] == "table" and x.get("defined", True) and not x.get("adopted", False)]

    # ---- what the generator asks for ------------------------------------------------------
    def phase(self, name: str) -> str:
        """The SQL of one deployment phase: the method `phase_<name>`."""
        return getattr(self, "phase_" + name.replace("-", "_"))()

    def check(self, scope: str, name: str, **item) -> str:
        """The SQL of one check: the method `check_<scope>_<name>`."""
        return getattr(self, f"check_{scope}_{name.replace('-', '_')}")(**item)
