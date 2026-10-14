"""Keep reusable bindings and example inputs separate from generated products."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[3]


PLATFORMS=tuple(p.name for p in sorted((ROOT/'examples/it-service-desk-data-product').iterdir()) if (p/'placement.json').exists())
assert PLATFORMS, 'No binding placement inputs found'

class BindingPackage(unittest.TestCase):
    def test_platform_bindings_are_templates_not_product_compilers(self):
        for platform in PLATFORMS:
            base=ROOT/'implementation'/platform
            for old in ('model.py','render.py','checks.py','validate.py','temporal.py'):
                self.assertFalse((base/old).exists(),f'Product compiler leaked into binding: {base/old}')
            templates=list(base.rglob('*.sql.j2'))
            self.assertTrue(templates)
            for path in templates:
                self.assertNotIn('customer360',path.read_text(encoding='utf-8').lower())
            for module in ('domain','semantic','memory','observability','search','prediction'):
                self.assertTrue((base/'modules'/module/'README.md').exists())
                self.assertTrue(list((base/'modules'/module).glob('*.sql.j2')))

    def test_platform_directories_hold_only_jinja_and_declarations(self):
        self.assertIn('duckdb',PLATFORMS)
        for platform in PLATFORMS:
            base=ROOT/'implementation'/platform
            self.assertEqual([str(p.relative_to(base)) for p in base.rglob('*.sql')],[],'Plain SQL is not a binding artefact')
            self.assertEqual([str(p.relative_to(base)) for p in base.rglob('*.py')],[],'Binding directories hold no compilers')
            for name in ('README.md','PLATFORM_PROFILE.md','CONFORMANCE.md','TEMPLATE_INPUTS.md'):
                self.assertTrue((base/name).exists(),f'{platform} lacks {name}')
            for pattern in ('object-placement','temporal-lifecycle-metadata','validation','access-layer','physical-storage'):
                self.assertTrue((base/'patterns'/pattern/'README.md').exists(),f'{platform} lacks pattern {pattern}')

    def test_templates_use_only_jinja_substitution_and_no_product_literals(self):
        masked=re.compile(r'\{#.*?#\}|\{\{.*?\}\}|\{%.*?%\}',re.S)
        other_conventions=[('format placeholder',re.compile(r'(?<![{$])\{[A-Za-z_][A-Za-z_0-9.]*\}')),
                           ('shell or dollar-brace token',re.compile(r'\$\{[^}]*\}')),
                           ('angle-bracket token',re.compile(r'<[A-Za-z_][A-Za-z_0-9 ]*>')),
                           ('dunder marker',re.compile(r'__[A-Z][A-Z_0-9]*__')),
                           ('printf placeholder',re.compile(r'%\([A-Za-z_]+\)s|%s|%d')),
                           ('at-marker',re.compile(r'@[A-Za-z_]+@')),
                           ('colon-named parameter',re.compile(r'(?<![:\w]):[A-Za-z_][A-Za-z_0-9]*\b(?!\s*\()'))]
        literals=re.compile(r'customer360|itsd|laboratory|lab_store|lab_public',re.I)
        for platform in PLATFORMS:
            base=ROOT/'implementation'/platform
            for path in list(base.rglob('*.sql.j2'))+list(base.rglob('*.json')):
                text=path.read_text(encoding='utf-8')
                self.assertIsNone(literals.search(text),f'Product literal in {path}')
                if path.name.endswith('.j2'):
                    stripped=masked.sub('',text)
                    stripped=re.sub(r"'(?:[^']|'')*'",'',stripped)
                    for label,pattern in other_conventions:
                        match=pattern.search(stripped)
                        self.assertIsNone(match,f'{label} {match and match.group(0)!r} in {path}')

    def test_examples_are_shared_inputs_not_generated_sql(self):
        base=ROOT/'examples/it-service-desk-data-product'
        self.assertTrue((base/'bindings/context.json').exists())
        for platform in PLATFORMS:
            self.assertTrue((base/platform/'placement.json').exists())
            self.assertFalse(list((base/platform).glob('*.sql')))
            self.assertFalse((ROOT/'examples'/('customer360-'+platform)/'build.sql').exists())


if __name__=='__main__':unittest.main()
