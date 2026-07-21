"""Guarded DataHub document write-back through the official MCP server."""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .domain import ChangePlan, DbtContract
from .mcp_catalog import CatalogLookupError, McpCatalogReader, ToolCaller, _decode_result
from .planner import build_change_plan, render_markdown


class WritebackError(RuntimeError):
    """Raised when confirmation, mutation, or verification fails."""


@dataclass(frozen=True)
class WritebackReceipt:
    document_urn: str
    title: str
    plan_sha256: str
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    raise WritebackError(f"{label} returned a non-object MCP payload")


def _document_payload(plan: ChangePlan) -> tuple[str, str, str]:
    plan_hash = plan.plan_sha256
    if not re.fullmatch(r"[0-9a-f]{64}", plan_hash):
        raise WritebackError("plan contains an invalid SHA-256 confirmation token")
    urn = f"urn:li:document:contract-bridge-{plan_hash}"
    title = f"Contract review: {plan.contract.relation_name} [{plan_hash[:12]}]"
    content = render_markdown(plan)
    if len(content) > 7_000:
        raise WritebackError("rendered plan exceeds the 7,000-character verified write-back limit")
    return urn, title, content


@dataclass
class McpPlanWriter:
    caller: ToolCaller

    async def _call_raw(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self.caller.call_tool(name, arguments)
        if getattr(result, "isError", False) or getattr(result, "is_error", False):
            raise WritebackError(f"DataHub MCP tool {name} reported an error")
        return result

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        return _decode_result(await self._call_raw(name, arguments), name)

    async def write(
        self, plan: ChangePlan, confirmation: str
    ) -> tuple[str, str, str]:
        if not secrets.compare_digest(plan.plan_sha256, confirmation.strip().lower()):
            raise WritebackError(
                "confirmation hash does not match the freshly recomputed live plan; "
                f"expected {plan.plan_sha256}"
            )

        urn, title, content = _document_payload(plan)
        save_result = _mapping(
            await self._call(
                "save_document",
                {
                    "document_type": "Decision",
                    "title": title,
                    "content": content,
                    "urn": urn,
                    "topics": ["contract-bridge", "dbt-contract", "change-review"],
                    "related_assets": [plan.catalog.dataset_urn],
                },
            ),
            "save_document",
        )
        if save_result.get("success") is not True:
            message = str(save_result.get("message") or "unknown failure")
            raise WritebackError(f"save_document did not confirm success: {message}")
        if save_result.get("urn") != urn:
            raise WritebackError("save_document returned a different document URN")

        return urn, title, content

    async def verify(
        self, plan: ChangePlan, urn: str, title: str, content: str
    ) -> WritebackReceipt:

        reread = _mapping(
            await self._call(
                "grep_documents",
                {
                    "urns": [urn],
                    "pattern": "(?s).*",
                    "context_chars": 7_000,
                    "max_matches_per_doc": 1,
                    "start_offset": 0,
                },
            ),
            "grep_documents",
        )
        documents = reread.get("results")
        if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
            raise WritebackError("grep_documents returned an invalid results payload")
        if len(documents) != 1:
            raise WritebackError(
                f"grep_documents returned {len(documents)} documents; expected exactly one"
            )
        document = _mapping(documents[0], "grep_documents.results[0]")
        matches = document.get("matches")
        if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
            raise WritebackError("grep_documents returned an invalid matches payload")
        if len(matches) != 1:
            raise WritebackError(
                f"grep_documents returned {len(matches)} excerpts; expected exactly one"
            )
        match = _mapping(matches[0], "grep_documents.results[0].matches[0]")
        if document.get("urn") != urn:
            raise WritebackError("re-read returned a different document URN")
        if document.get("title") != title:
            raise WritebackError("re-read document title does not match the written plan")
        if match.get("position") != 0:
            raise WritebackError("re-read did not return the complete document content")
        if match.get("excerpt") != content:
            raise WritebackError("re-read document content does not match the written plan")

        # The official tool only includes content_length when start_offset is non-zero.
        # A second overlapping read therefore proves the server-reported original length
        # while retaining the first call's byte-identical verification from character 0.
        length_reread = _mapping(
            await self._call(
                "grep_documents",
                {
                    "urns": [urn],
                    "pattern": "(?s).*",
                    "context_chars": 7_000,
                    "max_matches_per_doc": 1,
                    "start_offset": 1,
                },
            ),
            "grep_documents length check",
        )
        length_documents = length_reread.get("results")
        if (
            not isinstance(length_documents, Sequence)
            or isinstance(length_documents, (str, bytes))
            or len(length_documents) != 1
        ):
            raise WritebackError("grep_documents length check returned an invalid result")
        length_document = _mapping(
            length_documents[0], "grep_documents length check results[0]"
        )
        length_matches = length_document.get("matches")
        if (
            not isinstance(length_matches, Sequence)
            or isinstance(length_matches, (str, bytes))
            or len(length_matches) != 1
        ):
            raise WritebackError("grep_documents length check returned an invalid excerpt")
        length_match = _mapping(
            length_matches[0], "grep_documents length check results[0].matches[0]"
        )
        if (
            length_document.get("urn") != urn
            or length_document.get("title") != title
            or length_document.get("content_length") != len(content)
            or length_match.get("position") != 1
            or length_match.get("excerpt") != content[1:]
        ):
            raise WritebackError("re-read document length check does not match the written plan")

        return WritebackReceipt(urn, title, plan.plan_sha256, True)

    async def write_and_verify(self, plan: ChangePlan, confirmation: str) -> WritebackReceipt:
        """Write and verify with one caller; primarily useful for deterministic tests."""

        urn, title, content = await self.write(plan, confirmation)
        return await self.verify(plan, urn, title, content)


async def apply_plan_via_stdio(
    contract: DbtContract,
    confirmation: str,
    command: str = "mcp-server-datahub",
    arguments: Sequence[str] = (),
) -> tuple[ChangePlan, WritebackReceipt]:
    """Read live context, confirm its exact plan, write once, and verify by re-read."""

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise WritebackError("install the project with the 'mcp' extra") from exc

    environment = os.environ.copy()
    environment["TOOLS_IS_MUTATION_ENABLED"] = "true"
    environment["SAVE_DOCUMENT_TOOL_ENABLED"] = "true"
    # The official server treats any caller-supplied URN as an update, including the
    # first creation of a deterministic URN. Its Shared-folder update guard therefore
    # rejects a not-yet-existing document before save_document can create it. This
    # session disables that location guard; McpPlanWriter still permits only the
    # plan-derived URN and verifies the returned URN, title, and full content.
    environment["SAVE_DOCUMENT_RESTRICT_UPDATES"] = "false"
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
        required = {
            "get_entities",
            "get_lineage",
            "list_schema_fields",
            "save_document",
            "search",
        }
        missing = sorted(required - names)
        if missing:
            raise WritebackError(
                "DataHub MCP server is missing required tools: " + ", ".join(missing)
            )
        try:
            context = await McpCatalogReader(session).read_context(contract.relation_name)
        except CatalogLookupError as exc:
            raise WritebackError(str(exc)) from exc
        plan = build_change_plan(contract, context)
        urn, title, content = await McpPlanWriter(session).write(plan, confirmation)

    # DataHub OSS filters document tools when an MCP process starts before its first
    # document exists. Start a fresh, read-only process after save_document so the
    # official server can expose grep_documents, and allow bounded search-index lag.
    verify_environment = os.environ.copy()
    verify_environment.pop("TOOLS_IS_MUTATION_ENABLED", None)
    verify_environment.pop("SAVE_DOCUMENT_TOOL_ENABLED", None)
    verify_environment.pop("SAVE_DOCUMENT_RESTRICT_UPDATES", None)
    verify_parameters = StdioServerParameters(
        command=command,
        args=list(arguments),
        env=verify_environment,
    )
    for attempt in range(1, 7):
        async with (
            stdio_client(verify_parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            if "grep_documents" in {tool.name for tool in listed.tools}:
                receipt = await McpPlanWriter(session).verify(plan, urn, title, content)
                return plan, receipt
        if attempt < 6:
            await asyncio.sleep(10)

    raise WritebackError(
        "DataHub MCP server did not expose grep_documents after the bounded indexing wait"
    )


def render_receipt(receipt: WritebackReceipt) -> str:
    return json.dumps(receipt.to_dict(), sort_keys=True)
