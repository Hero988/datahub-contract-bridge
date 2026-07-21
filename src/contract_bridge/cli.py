"""Command-line entry point. Live MCP transport is added behind the same planner API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fixture import read_catalog_fixture
from .manifest import read_contracts
from .planner import build_change_plan, render_markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datahub-contract-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="create a read-only contract change plan")
    plan.add_argument("--manifest", required=True, type=Path)
    plan.add_argument("--catalog-fixture", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        contracts = read_contracts(args.manifest)
        if not contracts:
            raise SystemExit("manifest contains no enabled, enforced model contracts")
        if len(contracts) != 1:
            raise SystemExit("v0.1 requires exactly one enforced contract per plan")
        context = read_catalog_fixture(args.catalog_fixture, contracts[0].relation_name)
        plan = build_change_plan(contracts[0], context)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "plan.json").write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.output / "plan.md").write_text(render_markdown(plan), encoding="utf-8")
        print(plan.plan_sha256)
        return 0
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
