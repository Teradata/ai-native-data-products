"""Render the Teradata binding's Jinja templates for tests.

Every Teradata artefact is a Jinja template (Platform Implementation Authoring Standard
section 6), so a test never reads SQL from disk directly: it renders the template here,
under `StrictUndefined`, against a representative build context. A variable a template
reads and this context does not supply is an error, never an empty string.

`CONTEXT` is a representative, deliberately unremarkable context, not a product: the
names are fixtures. Tests that need a different value pass overrides to `render`.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[3]
TERADATA = REPO_ROOT / "implementation" / "teradata"

# Container and principal names every template may read. Placement and naming are the
# organisation's, so a template takes them from here rather than composing them.
CONTEXT = {
    "product": "Fixture",
    "modules": ["semantic", "memory", "domain", "observability", "search", "prediction"],
    "db": "FixtureObs",
    "semantic_db": "FixtureSem",
    "memory_db": "FixtureMem",
    "domain_db": "FixtureDom",
    "observability_db": "FixtureObs",
    "search_db": "FixtureSrch",
    "prediction_db": "FixturePred",
    "access_db": "FixtureAcc",
    "governance_db": "FixtureGov",
    "stage": "FixtureStage",
    "role_read": "FixtureRead",
    "role_agent": "FixtureAgent",
    "role_admin": "FixtureAdmin",
    "agent_service_account": "svc_fixture_agent",
    "analyst_user_or_group_role": "grp_fixture_analyst",
    "product_owner_user": "usr_fixture_owner",
    # The worked SCD2 table the temporal pattern's specimen templates render.
    "entity": "contract",
    "natural_key": "contract_bk",
    "surrogate_key": "contract_sk",
    "governed_view": "v_contract",
    "current_view": "contract_current",
    # Documentation-capture records (modules/memory/12-capture-protocol.sql.j2).
    "registered_modules": [], "decisions": [], "superseded": [], "changes": [],
    "glossary_terms": [], "recipes": [],
    "supports_deletion": True,
    "attributes": [
        {"name": "contract_status", "type": "VARCHAR(20)", "comment": "Contract status."},
        {"name": "premium_amount", "type": "DECIMAL(18,2)", "comment": "Premium amount."},
    ],
}


def environment():
    return Environment(loader=FileSystemLoader(str(TERADATA)),
                       keep_trailing_newline=True, undefined=StrictUndefined)


def template_name(path):
    """The loader-relative name of a template, from a path or a name."""
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(TERADATA)
    return path.as_posix()


def render(path, **overrides):
    """Render one Teradata template under StrictUndefined with the shared context."""
    context = dict(CONTEXT)
    context.update(overrides)
    return environment().get_template(template_name(path)).render(**context)
