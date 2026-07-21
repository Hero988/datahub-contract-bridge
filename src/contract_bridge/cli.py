"""Command-line entry point. Live MCP transport is added behind the same planner API."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .domain import CatalogContext, DbtContract
from .fixture import read_catalog_fixture
from .manifest import read_contracts
from .mcp_catalog import read_catalog_via_stdio
from .planner import build_change_plan, render_markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datahub-contract-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="create a read-only contract change plan")
    plan.add_argument("--manifest", required=True, type=Path)
    plan.add_argument("--catalog-fixture", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    plan_mcp = subparsers.add_parser(
        "plan-mcp", help="create a read-only plan through the official DataHub MCP server"
    )
    plan_mcp.add_argument("--manifest", required=True, type=Path)
    plan_mcp.add_argument("--output", required=True, type=Path)
    plan_mcp.add_argument("--mcp-command", default="mcp-server-datahub")
    plan_mcp.add_argument("--mcp-arg", action="append", default=[])
    return parser


def _single_contract(manifest: Path) -> DbtContract:
    contracts = read_contracts(manifest)
    if not contracts:
        raise SystemExit("manifest contains no enabled, enforced model contracts")
    if len(contracts) != 1:
        raise SystemExit("v0.1 requires exactly one enforced contract per plan")
    return contracts[0]


def _write_plan(contract: DbtContract, context: CatalogContext, output: Path) -> str:
    plan = build_change_plan(contract, context)
    output.mkdir(parents=True, exist_ok=True)
    (output / "plan.json").write_text(
        json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "plan.md").write_text(render_markdown(plan), encoding="utf-8")
    return plan.plan_sha256


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        contract = _single_contract(args.manifest)
        context = read_catalog_fixture(args.catalog_fixture, contract.relation_name)
        print(_write_plan(contract, context, args.output))
        return 0
    if args.command == "plan-mcp":
        contract = _single_contract(args.manifest)
        context = asyncio.run(
            read_catalog_via_stdio(
                contract.relation_name,
                command=args.mcp_command,
                arguments=args.mcp_arg,
            )
        )
        print(_write_plan(contract, context, args.output))
        return 0
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
