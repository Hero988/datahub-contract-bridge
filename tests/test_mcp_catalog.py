import asyncio
from collections import defaultdict

import pytest

from contract_bridge.mcp_catalog import CatalogLookupError, McpCatalogReader

DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,warehouse.analytics.orders,PROD)"
ARCHIVE_URN = (
    "urn:li:dataset:"
    "(urn:li:dataPlatform:snowflake,warehouse.analytics.orders_archive,PROD)"
)
BIGQUERY_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:bigquery,warehouse.analytics.orders,PROD)"
)


class FakeCaller:
    def __init__(self, responses):
        self.responses = {name: list(values) for name, values in responses.items()}
        self.calls = defaultdict(list)

    async def call_tool(self, name, arguments):
        self.calls[name].append(arguments)
        return self.responses[name].pop(0)


def test_reader_composes_exact_official_tool_context() -> None:
    caller = FakeCaller(
        {
            "search": [
                {
                    "searchResults": [
                        {
                            "entity": {
                                "urn": ARCHIVE_URN,
                                "properties": {"name": "warehouse.analytics.orders_archive"},
                            }
                        },
                        {"entity": {"urn": DATASET_URN, "properties": {"name": "orders"}}},
                    ]
                }
            ],
            "list_schema_fields": [
                {
                    "fields": [{"fieldPath": "order_id", "nativeDataType": "BIGINT"}],
                    "returned": 1,
                    "remainingCount": 1,
                },
                {
                    "fields": [{"fieldPath": "net_total", "type": "NUMBER"}],
                    "returned": 1,
                    "remainingCount": 0,
                },
            ],
            "get_entities": [
                {
                    "urn": DATASET_URN,
                    "ownership": {
                        "owners": [
                            {"owner": {"urn": "urn:li:corpGroup:data-platform"}},
                            {"owner": {"urn": "urn:li:corpGroup:data-platform"}},
                        ]
                    },
                }
            ],
            "get_lineage": [
                {
                    "downstreams": {
                        "total": 1,
                        "returned": 1,
                        "hasMore": False,
                        "searchResults": [
                            {
                                "entity": {
                                    "urn": "urn:li:dashboard:(looker,finance-revenue)",
                                    "properties": {"name": "Finance revenue"},
                                }
                            }
                        ],
                    }
                }
            ],
        }
    )

    context = asyncio.run(McpCatalogReader(caller).read_context("warehouse.analytics.orders"))

    assert context.dataset_urn == DATASET_URN
    assert [(field.name, field.data_type) for field in context.fields] == [
        ("order_id", "BIGINT"),
        ("net_total", "NUMBER"),
    ]
    assert context.owners == ("urn:li:corpGroup:data-platform",)
    assert context.downstream[0].name == "Finance revenue"
    assert context.downstream[0].entity_type == "DASHBOARD"
    assert caller.calls["search"][0]["filter"] == "entity_type = dataset"
    assert caller.calls["list_schema_fields"][1]["offset"] == 1
    assert caller.calls["get_lineage"][0]["upstream"] is False


def test_reader_rejects_ambiguous_exact_dataset() -> None:
    caller = FakeCaller(
        {
            "search": [
                {
                    "searchResults": [
                        {"entity": {"urn": DATASET_URN}},
                        {
                            "entity": {
                                "urn": BIGQUERY_URN
                            }
                        },
                    ]
                }
            ]
        }
    )

    with pytest.raises(CatalogLookupError, match="2 exact datasets"):
        asyncio.run(McpCatalogReader(caller).read_context("warehouse.analytics.orders"))


def test_reader_rejects_unbounded_downstream_context() -> None:
    caller = FakeCaller(
        {
            "search": [{"searchResults": [{"entity": {"urn": DATASET_URN}}]}],
            "list_schema_fields": [
                {"fields": [{"fieldPath": "order_id"}], "remainingCount": 0}
            ],
            "get_entities": [{"urn": DATASET_URN}],
            "get_lineage": [{"downstreams": {"total": 101, "searchResults": []}}],
        }
    )

    with pytest.raises(CatalogLookupError, match="narrow the lineage window"):
        asyncio.run(McpCatalogReader(caller).read_context("warehouse.analytics.orders"))
