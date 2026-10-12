"""Keep reusable bindings, their inputs and generated products apart.

A binding is Jinja templates plus the declarations in its PLATFORM_PROFILE.md; the inputs are
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

PLATFORMS = tuple(p.name for p in sorted((ROOT / "implementation").iterdir())
                  if (p / "PLATFORM_PROFILE.md").exists() and load_binding(p.name)[0]
                  and load_binding(p.name)[0].phases)
assert PLATFORMS, "No binding declares its phases"
EXAMPLE = ROOT / "examples" / "it-service-desk-data-product"


class BindingPackage(unittest.TestCase):
    def test_platform_bindings_are_templates_not_product_compilers(self):
        for platform in PLATFORMS:
            base = ROOT / "implementation" / platform
            templates = list(base.rglob("*.sql.j2"))
            self.assertTrue(templates)
            for path in templates:
                self.assertNotIn("customer360", path.read_text(encoding="utf-8").lower())
            for module in ("domain", "semantic", "memory", "observability", "search", "prediction"):
                self.assertTrue((base / "modules" / module / "README.md").exists())
                self.assertTrue(list((base / "modules" / module).glob("*.sql.j2")))

    def test_platform_directories_hold_only_jinja_and_declarations(self):
        for platform in PLATFORMS:
            base = ROOT / "implementation" / platform
            self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.sql")], [],
                             "Plain SQL is not a binding artefact")
            self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.py")], [],
                             "Binding directories hold no compilers")
            self.assertEqual([str(p.relative_to(base)) for p in base.rglob("*.json")], [],
                             "Bindings declare their inputs in PLATFORM_PROFILE.md, not JSON")
            for name in ("README.md", "PLATFORM_PROFILE.md", "CONFORMANCE.md"):
                self.assertTrue((base / name).exists(), f"{platform} lacks {name}")
            for pattern in ("object-placement", "temporal-lifecycle-metadata", "validation", "access-layer",
                            "physical-storage"):
                self.assertTrue((base / "patterns" / pattern / "README.md").exists(),
                                f"{platform} lacks pattern {pattern}")

    def test_every_template_is_declared_or_caller_rendered(self):
        """A template no phase, check or caller reaches is dead weight that drifts."""
        caller_rendered = {"modules/domain/02-key-allocation.sql.j2",
                           "patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2",
                           "patterns/temporal-lifecycle-metadata/00-macros.sql.j2"}
        for platform in PLATFORMS:
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
        """The example holds a specification and organisation profiles: no rendered SQL and no
        binding-specific input files, which a build context replaces."""
        self.assertTrue((EXAMPLE / "design-output" / "design_specification.md").exists())
        for platform in PLATFORMS:
            self.assertTrue((EXAMPLE / "profiles" / f"{platform}.md").exists(),
                            f"no organisation profile for {platform}")
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.sql")], [])
        self.assertEqual([p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*.json")], [])


if __name__ == "__main__":
    unittest.main()
