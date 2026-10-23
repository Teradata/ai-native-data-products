"""Keep reusable bindings, their inputs and generated products apart.

A binding is Jinja templates, the declarations in its binding.toml, and one README with a
section per module and pattern; the inputs are
a design specification and an organisation profile; what a build renders lives outside this
repository. Platforms are discovered from the bindings that declare their phases, never listed.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tooling" / "build"))

from binding import load_binding  # noqa: E402
from org_profile import example_targets  # noqa: E402

PLATFORMS = tuple(p.name for p in sorted((ROOT / "implementation").iterdir())
                  if (p / "binding.toml").exists() and load_binding(p.name)[0]
                  and load_binding(p.name)[0].phases)
assert PLATFORMS, "No binding declares its phases"
EXAMPLE = ROOT / "examples" / "it-service-desk-data-product"
MODULES = ("memory", "semantic", "domain", "observability", "search", "prediction")
PATTERNS = ("object-placement", "temporal-lifecycle-metadata", "validation", "access-layer", "physical-storage")
SECTION = re.compile(r"^## (\d+)\. .*\(`([a-z-]+)`\)\s*$", re.M)


def sections(platform):
    """The README's numbered module and pattern sections, by anchor."""
    text = (ROOT / "implementation" / platform / "README.md").read_text(encoding="utf-8")
    return {anchor: int(n) for n, anchor in SECTION.findall(text)}


class BindingPackage(unittest.TestCase):
    def test_platform_bindings_are_templates_not_product_compilers(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = ROOT / "implementation" / platform
                templates = list(base.rglob("*.sql.j2"))
                self.assertTrue(templates)
                for path in templates:
                    self.assertNotIn("customer360", path.read_text(encoding="utf-8").lower())
                for module in MODULES:
                    self.assertTrue(list((base / "modules" / module).glob("*.sql.j2")))

    def test_platform_directories_hold_only_jinja_and_declarations(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = ROOT / "implementation" / platform
                self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.sql")], [],
                                 "Plain SQL is not a binding artefact")
                self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.py")], [],
                                 "Binding directories hold no compilers")
                self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.json")], [],
                                 "Bindings declare their inputs in binding.toml, not JSON")
                for name in ("README.md", "PLATFORM_PROFILE.md", "CONFORMANCE.md", "binding.toml"):
                    self.assertTrue((base / name).exists(), f"{platform} lacks {name}")
                self.assertEqual([p.relative_to(base).as_posix() for p in base.rglob("README.md")], ["README.md"],
                                 "A binding documents its modules and patterns as README sections, not files")

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

    def test_conformance_is_generated_and_status_follows_it(self):
        """Authoring Standard §8.1: the report is generated, never kept by hand, and a binding
        document is `standard` only when its binding's report is."""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = ROOT / "implementation" / platform
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

    def test_every_template_is_declared_or_caller_rendered(self):
        """A template no phase, check or caller reaches is dead weight that drifts."""
        caller_rendered = {"modules/domain/02-key-allocation.sql.j2",
                           "patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2",
                           "patterns/temporal-lifecycle-metadata/00-macros.sql.j2",
                           "modules/semantic/contract/00-macros.sql.j2"}
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                b, _ = load_binding(platform)
                base = ROOT / "implementation" / platform
                reached = set(b.phases.values()) | set(b.checks.values()) | {b.deploy} | caller_rendered
                for path in base.rglob("*.j2"):
                    rel = path.relative_to(base).as_posix()
                    self.assertIn(rel, reached, f"{platform}: {rel} is rendered by nothing")

    def test_templates_use_only_jinja_substitution_and_no_product_literals(self):
        masked = re.compile(r"\{#.*?#\}|\{\{.*?\}\}|\{%.*?%\}", re.S)
        other_conventions = [("format placeholder", re.compile(r"(?<![{$])\{[A-Za-z_][A-Za-z_0-9.]*\}")),
                             ("shell or dollar-brace token", re.compile(r"\$\{[^}]*\}")),
                             ("angle-bracket token", re.compile(r"<[A-Za-z_][A-Za-z_0-9 ]*>")),
                             ("dunder marker", re.compile(r"__[A-Z][A-Z_0-9]*__")),
                             ("printf placeholder", re.compile(r"%\([A-Za-z_]+\)s|%s|%d")),
                             ("at-marker", re.compile(r"@[A-Za-z_]+@")),
                             ("colon-named parameter", re.compile(r"(?<![:\w]):[A-Za-z_][A-Za-z_0-9]*\b(?!\s*\()"))]
        literals = re.compile(r"customer360|itsd|custord|laboratory|lab_store|lab_public", re.I)
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                base = ROOT / "implementation" / platform
                for path in base.rglob("*.j2"):
                    text = path.read_text(encoding="utf-8")
                    self.assertIsNone(literals.search(text), f"Product literal in {path}")
                    stripped = masked.sub("", text)
                    stripped = re.sub(r"'(?:[^']|'')*'", "", stripped)
                    for label, pattern in other_conventions:
                        match = pattern.search(stripped)
                        self.assertIsNone(match, f"{label} {match and match.group(0)!r} in {path}")

    def test_examples_are_build_inputs_not_generated_output(self):
        """The example holds a specification and configurations: no rendered SQL and no
        binding-specific input files, which a build context replaces. Every binding has a
        target in the template configuration, so the reference products build on it."""
        self.assertTrue((EXAMPLE / "design-output" / "design_specification.md").exists())
        template = {p for c, p in example_targets() if c.label(c.implementation) == "config/implementation.example.toml"}
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                self.assertIn(platform, template, f"config/implementation.example.toml has no target for {platform}")
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.sql")], [])
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.json")], [])


if __name__ == "__main__":
    unittest.main()
