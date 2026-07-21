# DataHub Contract Bridge

Turn enforced dbt contracts into lineage-aware, reviewable DataHub change plans.

This project is a new Apache-2.0 entry for the 2026 **Build with DataHub: The Agent
Hackathon**. It is under active development. The current v0.1 milestone parses a dbt
`manifest.json`, includes only tests explicitly tagged `contract`, compares the desired
contract with deterministic catalog context, surfaces removals/additions/type changes,
adds downstream and owner context, and emits JSON plus Markdown with a stable SHA-256
confirmation token.

The next milestone connects the same planner to DataHub's official MCP server for exact
asset resolution, schema, lineage and owner reads, followed by an explicitly confirmed
write-back and re-read. Offline fixtures are not presented as a live integration.

## Why this exists

DataHub already provides lineage, impact analysis and data contracts. Acryl's existing
`dbt-impact-action` already adds impact summaries to pull requests. Contract Bridge does
not rebuild either. It composes dbt contract intent, exact catalog resolution,
lineage/owner review and guarded durable write-back into one auditable workflow.

The wedge is grounded in [DataHub issue #11927](https://github.com/datahub-project/datahub/issues/11927),
where Checkout.com described its custom mapping between dbt contracts and DataHub data
contracts. Contract Bridge remains an external interoperable tool while DataHub's native
contract feature evolves.

## Run the offline milestone

```bash
python -m contract_bridge.cli plan \
  --manifest tests/fixtures/manifest.json \
  --catalog-fixture tests/fixtures/catalog.json \
  --output artifacts/demo
```

The command prints the plan hash and writes `artifacts/demo/plan.json` and
`artifacts/demo/plan.md`. No mutation occurs.

## Test

```bash
python -m pytest
ruff check .
```

## Safety model

- Synthetic metadata in examples and tests; no customer or production data.
- Endpoint and token will be accepted only through environment variables and are never
  serialized into plans.
- DataHub access is read-only by default.
- A write requires the exact displayed plan SHA-256 and is followed by a re-read.
- The tool never claims a contract or write succeeded without the corresponding API
  response and verification.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
