"""Keep reusable bindings and example inputs separate from generated products."""
from pathlib import Path
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

    def test_examples_are_shared_inputs_not_generated_sql(self):
        base=ROOT/'examples/it-service-desk-data-product'
        self.assertTrue((base/'bindings/context.json').exists())
        for platform in PLATFORMS:
            self.assertTrue((base/platform/'placement.json').exists())
            self.assertFalse(list((base/platform).glob('*.sql')))
            self.assertFalse((ROOT/'examples'/('customer360-'+platform)/'build.sql').exists())


if __name__=='__main__':unittest.main()
