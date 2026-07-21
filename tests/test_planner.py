from __future__ import annotations

from pathlib import Path

from contract_bridge.fixture import read_catalog_fixture
from contract_bridge.manifest import read_contracts
from contract_bridge.planner import build_change_plan, render_markdown

FIXTURES = Path(__file__).parent / "fixtures"


def test_plan_is_stable_and_surfaces_contract_risks() -> None:
    contract = read_contracts(FIXTURES / "manifest.json")[0]
    catalog = read_catalog_fixture(FIXTURES / "catalog.json", contract.relation_name)

    first = build_change_plan(contract, catalog)
    second = build_change_plan(contract, catalog)

    assert first.plan_sha256 == second.plan_sha256
    assert len(first.plan_sha256) == 64
    assert [(risk.code, risk.subject) for risk in first.risks] == [
        ("FIELD_REMOVAL", "status"),
        ("FIELD_ADDITION", "net_total"),
        ("TYPE_CHANGE", "customer_id"),
        ("DOWNSTREAM_IMPACT", catalog.dataset_urn),
    ]
    markdown = render_markdown(first)
    assert first.plan_sha256 in markdown
    assert "Mutation is not authorized" in markdown


def test_plan_dict_contains_no_environment_or_credentials() -> None:
    contract = read_contracts(FIXTURES / "manifest.json")[0]
    catalog = read_catalog_fixture(FIXTURES / "catalog.json", contract.relation_name)
    rendered = str(build_change_plan(contract, catalog).to_dict()).lower()

    assert "token" not in rendered
    assert "password" not in rendered
    assert "secret" not in rendered
