"""Read exact planning context through DataHub's official MCP server."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .domain import CatalogAsset, CatalogContext, CatalogField


class CatalogLookupError(RuntimeError):
    """Raised when MCP context is missing, ambiguous, or incomplete."""


class ToolCaller(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    raise CatalogLookupError(f"{label} returned a non-object MCP payload")


def _decode_result(result: Any, tool_name: str) -> Any:
    """Accept MCP SDK results and simple mappings used by deterministic tests."""

    if isinstance(result, Mapping):
        payload: Any = dict(result)
    else:
        payload = getattr(result, "structuredContent", None)
        if payload is None:
            payload = getattr(result, "structured_content", None)
        if payload is None:
            content = getattr(result, "content", None)
            texts = [item.text for item in content or () if hasattr(item, "text")]
            if len(texts) != 1:
                raise CatalogLookupError(f"{tool_name} returned no unambiguous JSON payload")
            try:
                payload = json.loads(texts[0])
            except json.JSONDecodeError as exc:
                raise CatalogLookupError(f"{tool_name} returned invalid JSON text") from exc

    if isinstance(payload, Mapping) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def _normalise_name(value: str) -> str:
    return ".".join(
        part.strip().strip('`"[]').lower()
        for part in value.strip().split(".")
        if part.strip()
    )


def _dataset_name_from_urn(urn: str) -> str | None:
    match = re.fullmatch(
        r"urn:li:dataset:\(urn:li:dataPlatform:[^,]+,(.+),[^,]+\)", urn
    )
    return match.group(1) if match else None


def _entity_name(entity: Mapping[str, Any]) -> str:
    properties = entity.get("properties")
    if isinstance(properties, Mapping) and properties.get("name"):
        return str(properties["name"])
    if entity.get("name"):
        return str(entity["name"])
    urn = str(entity.get("urn", ""))
    return _dataset_name_from_urn(urn) or urn


def _entity_type(entity: Mapping[str, Any]) -> str:
    if entity.get("type"):
        return str(entity["type"]).upper()
    urn = str(entity.get("urn", ""))
    match = re.match(r"urn:li:([^:]+):", urn)
    return match.group(1).replace("_", " ").upper() if match else "UNKNOWN"


@dataclass
class McpCatalogReader:
    """Compose the official search/schema/entity/lineage MCP tools."""

    caller: ToolCaller
    max_schema_fields: int = 1000
    max_downstream_assets: int = 100

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self.caller.call_tool(name, arguments)
        if getattr(result, "isError", False) or getattr(result, "is_error", False):
            raise CatalogLookupError(f"DataHub MCP tool {name} reported an error")
        return _decode_result(result, name)

    async def _resolve_exact_dataset(self, relation_name: str) -> str:
        terms = re.findall(r"[A-Za-z0-9]+", relation_name)
        if not terms:
            raise CatalogLookupError("dbt relation name contains no searchable terms")
        payload = _mapping(
            await self._call(
                "search",
                {
                    "query": "/q " + "+".join(terms),
                    "filter": "entity_type = dataset",
                    "num_results": 50,
                    "offset": 0,
                },
            ),
            "search",
        )
        results = payload.get("searchResults") or []
        target = _normalise_name(relation_name)
        matches: list[str] = []
        for item in results:
            if not isinstance(item, Mapping) or not isinstance(item.get("entity"), Mapping):
                continue
            entity = item["entity"]
            urn = str(entity.get("urn", ""))
            candidate_names = {_normalise_name(_entity_name(entity))}
            urn_name = _dataset_name_from_urn(urn)
            if urn_name:
                candidate_names.add(_normalise_name(urn_name))
            if target in candidate_names and urn:
                matches.append(urn)
        unique = list(dict.fromkeys(matches))
        if not unique:
            raise CatalogLookupError(
                f"DataHub search returned no exact dataset for {relation_name!r}"
            )
        if len(unique) != 1:
            raise CatalogLookupError(
                f"DataHub search returned {len(unique)} exact datasets for {relation_name!r}"
            )
        return unique[0]

    async def _schema(self, urn: str) -> tuple[CatalogField, ...]:
        fields: list[CatalogField] = []
        offset = 0
        while True:
            payload = _mapping(
                await self._call(
                    "list_schema_fields",
                    {"urn": urn, "limit": 100, "offset": offset},
                ),
                "list_schema_fields",
            )
            page = payload.get("fields") or []
            for raw in page:
                if not isinstance(raw, Mapping) or not raw.get("fieldPath"):
                    raise CatalogLookupError("DataHub schema contained a field without fieldPath")
                raw_type = raw.get("nativeDataType") or raw.get("type")
                if isinstance(raw_type, Mapping):
                    raw_type = raw_type.get("type")
                fields.append(
                    CatalogField(
                        str(raw["fieldPath"]), str(raw_type) if raw_type else None
                    )
                )
            if len(fields) > self.max_schema_fields:
                raise CatalogLookupError(
                    f"DataHub schema exceeds the {self.max_schema_fields}-field safety limit"
                )
            remaining = int(payload.get("remainingCount") or 0)
            returned = int(payload.get("returned", len(page)))
            if remaining <= 0:
                break
            if returned <= 0:
                raise CatalogLookupError("DataHub schema pagination made no progress")
            offset += returned
        return tuple(fields)

    async def _owners(self, urn: str) -> tuple[str, ...]:
        payload = _mapping(await self._call("get_entities", {"urns": urn}), "get_entities")
        ownership = payload.get("ownership")
        owner_rows = ownership.get("owners", []) if isinstance(ownership, Mapping) else []
        owners: list[str] = []
        for row in owner_rows:
            owner = row.get("owner") if isinstance(row, Mapping) else None
            if isinstance(owner, Mapping) and owner.get("urn"):
                owners.append(str(owner["urn"]))
        return tuple(dict.fromkeys(owners))

    async def _downstream(self, urn: str) -> tuple[CatalogAsset, ...]:
        assets: list[CatalogAsset] = []
        offset = 0
        while True:
            payload = _mapping(
                await self._call(
                    "get_lineage",
                    {
                        "urn": urn,
                        "upstream": False,
                        "max_hops": 1,
                        "max_results": self.max_downstream_assets,
                        "offset": offset,
                    },
                ),
                "get_lineage",
            )
            direction = payload.get("downstreams") or {}
            if not isinstance(direction, Mapping):
                raise CatalogLookupError("get_lineage returned invalid downstream context")
            total = direction.get("total")
            if isinstance(total, int) and total > self.max_downstream_assets:
                raise CatalogLookupError(
                    f"DataHub reports {total} downstream assets; narrow the lineage window"
                )
            rows = direction.get("searchResults") or []
            for row in rows:
                entity = row.get("entity") if isinstance(row, Mapping) else None
                if not isinstance(entity, Mapping) or not entity.get("urn"):
                    raise CatalogLookupError("DataHub lineage contained an asset without a URN")
                assets.append(
                    CatalogAsset(
                        urn=str(entity["urn"]),
                        name=_entity_name(entity),
                        entity_type=_entity_type(entity),
                    )
                )
            if len(assets) > self.max_downstream_assets:
                raise CatalogLookupError(
                    f"DataHub lineage exceeds the {self.max_downstream_assets}-asset safety limit"
                )
            if not direction.get("hasMore"):
                break
            returned = int(direction.get("returned", len(rows)))
            if returned <= 0:
                raise CatalogLookupError("DataHub lineage pagination made no progress")
            offset += returned
        deduplicated = {asset.urn: asset for asset in assets}
        return tuple(deduplicated.values())

    async def read_context(self, relation_name: str) -> CatalogContext:
        urn = await self._resolve_exact_dataset(relation_name)
        fields = await self._schema(urn)
        owners = await self._owners(urn)
        downstream = await self._downstream(urn)
        return CatalogContext(urn, fields, downstream, owners)


async def read_catalog_via_stdio(
    relation_name: str,
    command: str = "mcp-server-datahub",
    arguments: Sequence[str] = (),
) -> CatalogContext:
    """Launch the official DataHub MCP server and read one bounded context."""

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise CatalogLookupError("install the project with the 'mcp' extra") from exc

    environment = os.environ.copy()
    environment["TOOLS_IS_MUTATION_ENABLED"] = "false"
    parameters = StdioServerParameters(
        command=command,
        args=list(arguments),
        env=environment,
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        required = {"search", "list_schema_fields", "get_entities", "get_lineage"}
        missing = sorted(required - names)
        if missing:
            raise CatalogLookupError(
                "DataHub MCP server is missing required tools: " + ", ".join(missing)
            )
        return await McpCatalogReader(session).read_context(relation_name)
