import asyncio
from collections import defaultdict

import pytest

from contract_bridge.domain import (
    CatalogContext,
    CatalogField,
    ChangePlan,
    DbtContract,
    FieldSpec,
)
from contract_bridge.mcp_writeback import McpPlanWriter, WritebackError
from contract_bridge.planner import build_change_plan, render_markdown

DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,warehouse.orders,PROD)"


class FakeCaller:
    def __init__(self, responses):
        self.responses = {name: list(values) for name, values in responses.items()}
        self.calls = defaultdict(list)

    async def call_tool(self, name, arguments):
        self.calls[name].append(arguments)
        return self.responses[name].pop(0)


def _plan() -> ChangePlan:
    contract = DbtContract(
        "model.analytics.orders",
        "warehouse.orders",
        (FieldSpec("order_id", "bigint"),),
        (),
    )
    catalog = CatalogContext(
        DATASET_URN,
        (CatalogField("order_id", "BIGINT"),),
        (),
        ("urn:li:corpGroup:data-platform",),
    )
    return build_change_plan(contract, catalog)


def test_writer_requires_exact_fresh_hash_before_any_mutation() -> None:
    caller = FakeCaller({})

    with pytest.raises(WritebackError, match="does not match"):
        asyncio.run(McpPlanWriter(caller).write_and_verify(_plan(), "0" * 64))

    assert not caller.calls


def test_writer_uses_deterministic_urn_and_verifies_exact_reread() -> None:
    plan = _plan()
    urn = f"urn:li:document:contract-bridge-{plan.plan_sha256}"
    title = f"Contract review: {plan.contract.relation_name} [{plan.plan_sha256[:12]}]"
    content = render_markdown(plan)
    caller = FakeCaller(
        {
            "save_document": [
                {
                    "success": True,
                    "urn": urn,
                    "message": "updated",
                    "author": "Data Platform",
                }
            ],
            "grep_documents": [
                {
                    "results": [
                        {
                            "urn": urn,
                            "title": title,
                            "matches": [{"excerpt": content, "position": 0}],
                            "content_length": len(content),
                        }
                    ]
                }
            ],
        }
    )

    receipt = asyncio.run(McpPlanWriter(caller).write_and_verify(plan, plan.plan_sha256.upper()))

    assert receipt.verified is True
    assert receipt.document_urn == urn
    save = caller.calls["save_document"][0]
    assert save["urn"] == urn
    assert save["related_assets"] == [DATASET_URN]
    assert caller.calls["grep_documents"] == [
        {
            "urns": [urn],
            "pattern": "(?s).*",
            "context_chars": 7_000,
            "max_matches_per_doc": 1,
            "start_offset": 0,
        }
    ]


def test_writer_rejects_success_claim_when_reread_content_differs() -> None:
    plan = _plan()
    urn = f"urn:li:document:contract-bridge-{plan.plan_sha256}"
    title = f"Contract review: {plan.contract.relation_name} [{plan.plan_sha256[:12]}]"
    caller = FakeCaller(
        {
            "save_document": [{"success": True, "urn": urn}],
            "grep_documents": [
                {
                    "results": [
                        {
                            "urn": urn,
                            "title": title,
                            "matches": [{"excerpt": "stale content", "position": 0}],
                            "content_length": len(render_markdown(plan)),
                        }
                    ]
                }
            ],
        }
    )

    with pytest.raises(WritebackError, match="content does not match"):
        asyncio.run(McpPlanWriter(caller).write_and_verify(plan, plan.plan_sha256))


def test_writer_rejects_incomplete_reread() -> None:
    plan = _plan()
    urn = f"urn:li:document:contract-bridge-{plan.plan_sha256}"
    title = f"Contract review: {plan.contract.relation_name} [{plan.plan_sha256[:12]}]"
    content = render_markdown(plan)
    caller = FakeCaller(
        {
            "save_document": [{"success": True, "urn": urn}],
            "grep_documents": [
                {
                    "results": [
                        {
                            "urn": urn,
                            "title": title,
                            "matches": [{"excerpt": content[1:], "position": 1}],
                            "content_length": len(content),
                        }
                    ]
                }
            ],
        }
    )

    with pytest.raises(WritebackError, match="complete document content"):
        asyncio.run(McpPlanWriter(caller).write_and_verify(plan, plan.plan_sha256))
