"""Keep reusable bindings, their inputs and generated products apart.

A binding is one dialect module, the declarations in its binding.toml, and one README with a
section per module and pattern; the inputs are a design specification and an organisation's
configuration; what a build renders lives outside this repository. Platforms are discovered
from the directories that hold a binding.toml and a dialect.py, never listed.
"""
from pathlib import Path
import ast
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tooling" / "bindings"))
sys.path.insert(0, str(ROOT / "tooling" / "build"))

import build_context  # noqa: E402
from dialect import PORTABLE, dialect_class  # noqa: E402
from org_profile import example_targets  # noqa: E402
from render import dialect_for, render_context  # noqa: E402

IMPLEMENTATION = ROOT / "implementation"
PLATFORMS = tuple(p.name for p in sorted(IMPLEMENTATION.iterdir())
                  if (p / "binding.toml").exists() and (p / "dialect.py").exists())
assert PLATFORMS, "No binding has a dialect"
DIALECTS = [IMPLEMENTATION / "portable" / "dialect.py"] + [IMPLEMENTATION / p / "dialect.py" for p in PLATFORMS]
EXAMPLE = ROOT / "examples" / "it-service-desk-data-product"
SPECIFICATIONS = (EXAMPLE / "design-output" / "design_specification.md",
                  ROOT / "tooling" / "evals" / "reference" / "customer-orders.md")
MODULES = ("memory", "semantic", "domain", "observability", "search", "prediction")
PATTERNS = ("object-placement", "temporal-lifecycle-metadata", "validation", "access-layer", "physical-storage")
SECTION = re.compile(r"^## (\d+)\. .*\(`([a-z-]+)`\)\s*$", re.M)
BINDING_FILES = {"README.md", "PLATFORM_PROFILE.md", "CONFORMANCE.md", "binding.toml", "dialect.py"}
BINDING_BUDGET = 6
# What a dialect may import: the dialect it extends, and pure standard-library helpers.
IMPORTS = {"portable_dialect", "dialect", "json", "re"}
IO_CALLS = {"open", "print", "input", "eval", "exec", "compile", "__import__", "globals", "breakpoint"}
PRODUCT_LITERALS = re.compile(r"customer360|itsd|custord|laboratory|lab_store|lab_public", re.I)
CALLER_API = {"key_allocation", "maintenance", "insert"}


def sections(platform):
    """The README's numbered module and pattern sections, by anchor."""
    text = (IMPLEMENTATION / platform / "README.md").read_text(encoding="utf-8")
    return {anchor: int(n) for n, anchor in SECTION.findall(text)}


def methods(path):
    """Every method a dialect module defines: (class, name, first line). A decorated method's
    code starts at its first decorator."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [(c.name, f.name, min([f.lineno] + [d.lineno for d in f.decorator_list]))
            for c in tree.body if isinstance(c, ast.ClassDef)
            for f in c.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]


def reached():
    """The (file, first line) of every dialect function that generation calls: every phase,
    deploy script and check of every example build, and the caller API over every keymap and
    every entity with history."""
    seen = set()
    files = {str(p) for p in DIALECTS}

    def trace(frame, event, arg):
        if event == "call" and frame.f_code.co_filename in files:
            seen.add((frame.f_code.co_filename, frame.f_code.co_firstlineno))
        return None

    for configuration, platform in example_targets():
        for spec in SPECIFICATIONS:
            ctx, findings = build_context.resolve(spec, configuration)
            assert not findings, [str(f) for f in findings]
            sys.settrace(trace)
            try:
                render_context(ctx)
                dialect = dialect_for(ctx)
                for x in ctx["entities"]:
                    if x["kind"] == "Keymap":
                        dialect.key_allocation(x, natural_value="N-1")
                        dialect.key_allocation(x, staged={"container": None, "name": "stage", "column": "n"})
                    if x.get("history") and "table" in x.get("objects", {}):
                        row = {c["physical_name"]: None for c in x["columns"]}
                        for effective_at in (None, "2026-01-01T00:00:00+00:00"):
                            dialect.maintenance(x, 1, effective_at, "2026-01-01T00:00:00+00:00", [row])
            finally:
                sys.settrace(None)
    return seen


class BindingPackage(unittest.TestCase):
    def test_a_binding_is_one_dialect_and_its_declarations(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = IMPLEMENTATION / platform
                found = {p.relative_to(base).as_posix() for p in base.rglob("*")}
                self.assertEqual(sorted(BINDING_FILES - found), [], f"{platform} lacks a binding file")
                self.assertEqual(sorted(found - BINDING_FILES), [],
                                 "A binding holds its dialect, declarations and three documents; nothing else")
                self.assertLessEqual(len(found), BINDING_BUDGET, f"{platform} is over the binding budget")
        self.assertEqual(sorted(p.name for p in (IMPLEMENTATION / "portable").iterdir()), ["dialect.py"])

    def test_every_dialect_extends_the_portable_dialect(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                cls = dialect_class(platform)
                self.assertTrue(issubclass(cls, sys.modules[PORTABLE].PortableDialect))
                for phase in cls.PHASES:
                    self.assertTrue(callable(getattr(cls, "phase_" + phase.replace("-", "_"), None)),
                                    f"{platform}: phase {phase} has no method")
                for scope, name in cls.CHECKS:
                    self.assertTrue(callable(getattr(cls, f"check_{scope}_{name.replace('-', '_')}", None)),
                                    f"{platform}: check {scope} {name} has no method")

    def test_dialects_are_pure_and_hold_no_product_literals(self):
        """A dialect reads only the build context: no I/O, clock or environment, and no names
        of a product or organisation (Authoring Standard §6)."""
        for path in DIALECTS:
            with self.subTest(dialect=path.parent.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        self.assertEqual([a.name for a in node.names if a.name not in IMPORTS], [],
                                         f"line {node.lineno} imports outside the dialect's allowance")
                    elif isinstance(node, ast.ImportFrom):
                        self.assertIn(node.module, IMPORTS, f"line {node.lineno} imports {node.module}")
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, IO_CALLS, f"line {node.lineno} calls {node.func.id}")
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                        self.assertIsNone(PRODUCT_LITERALS.search(node.value),
                                          f"line {node.lineno} holds a product literal")

    def test_every_dialect_method_is_reached(self):
        """A method no phase, check or caller reaches is dead weight that drifts. A portable
        method every platform overrides is still the default a new platform inherits, and an
        abstract one exists to be overridden, so both count as reached."""
        seen = reached()
        overridden = {name for platform in PLATFORMS for _, name, _ in methods(IMPLEMENTATION / platform / "dialect.py")}
        portable = IMPLEMENTATION / "portable" / "dialect.py"
        for path in DIALECTS:
            with self.subTest(dialect=path.parent.name):
                dead = [f"{cls}.{name}" for cls, name, line in methods(path)
                        if (str(path), line) not in seen and name not in CALLER_API
                        and not (path == portable and name in overridden)]
                self.assertEqual(dead, [], f"{path.parent.name}: methods nothing reaches")

    def test_every_module_and_pattern_has_a_section_numbered_alike_on_every_binding(self):
        """Authoring Standard §5: one README section per module and pattern, numbered the same on
        every binding, since the role files cite them by number."""
        design = {p.stem for kind in ("modules", "patterns") for p in (ROOT / "design" / kind).glob("*.md")}
        numbering = {}
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                found = sections(platform)
                self.assertEqual(sorted(set(MODULES + PATTERNS) - set(found)), [],
                                 f"{platform}: README lacks a section")
                self.assertEqual(sorted(set(found) - design), [], f"{platform}: a section names no design anchor")
                self.assertEqual(sorted(found.values()), list(range(1, len(found) + 1)),
                                 f"{platform}: sections are not numbered 1 to {len(found)}")
                for anchor in MODULES + PATTERNS:
                    numbering.setdefault(anchor, set()).add(found[anchor])
        self.assertEqual({a: n for a, n in numbering.items() if len(n) > 1}, {},
                         "a section has a different number on different bindings")

    def test_every_platform_profile_keeps_its_sql_idioms_at_section_7(self):
        """Authoring Standard §5: roles/build.md sends every build to the profile's §7 before
        it writes SQL, so §7 is the SQL idioms on every binding, not whatever a profile put
        seventh."""
        route = (ROOT / "roles" / "build.md").read_text(encoding="utf-8")
        self.assertRegex(route, r"§7, SQL Idioms and Driver\s+Constraints")
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                profile = (IMPLEMENTATION / platform / "PLATFORM_PROFILE.md").read_text(encoding="utf-8")
                self.assertRegex(profile, r"(?m)^## 7\. SQL Idioms and Driver Constraints\s*$")

    def test_conformance_is_generated_and_status_follows_it(self):
        """Authoring Standard §8.1: the report is generated, never kept by hand, and a binding
        document is `standard` only when its binding's report is."""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = IMPLEMENTATION / platform
                report = (base / "CONFORMANCE.md").read_text(encoding="utf-8")
                self.assertTrue(report.startswith("<!-- Generated by tooling/bindings/conformance.py."),
                                f"{platform}: CONFORMANCE.md is not generated")
                status = re.search(r"^Status: \*\*(\w+)\*\*", report, re.M)
                self.assertTrue(status, f"{platform}: CONFORMANCE.md states no status")
                if status.group(1) != "standard":
                    claims = [p.relative_to(base).as_posix() for p in base.rglob("*.md")
                              if re.search(r"^status:\s*standard\s*$", p.read_text(encoding="utf-8")[:600], re.M)]
                    self.assertEqual(claims, [], f"{platform}: documents claim standard while the binding is "
                                                 f"{status.group(1)}")

    def test_examples_are_build_inputs_not_generated_output(self):
        """The example holds a specification and configurations: no rendered SQL and no
        binding-specific input files, which a build context replaces. Every binding has a
        target in the example configuration, so the reference products build on it."""
        self.assertTrue(SPECIFICATIONS[0].exists())
        example = {p for c, p in example_targets() if c.label(c.implementation) == "config/implementation.example.toml"}
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                self.assertIn(platform, example, f"config/implementation.example.toml has no target for {platform}")
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.sql")], [])
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.json")], [])


if __name__ == "__main__":
    unittest.main()
