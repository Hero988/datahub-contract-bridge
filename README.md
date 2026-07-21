# DataHub Contract Bridge

Turn enforced dbt contracts into lineage-aware, reviewable DataHub change plans.

This project is a new Apache-2.0 entry for the 2026 **Build with DataHub: The Agent
Hackathon**. It is under active development. The current read milestone parses a dbt
`manifest.json`, includes only tests explicitly tagged `contract`, resolves exactly one
DataHub dataset through the official MCP server, reads its schema, one-hop downstream
lineage and owners, then emits JSON plus Markdown with a stable SHA-256 confirmation
token. The same planner can run against deterministic catalog fixtures.

The MCP adapter is covered by deterministic transport-contract tests but has not yet
run against a live DataHub instance. Offline fixtures are not presented as a live
integration. The next milestone adds explicitly confirmed `save_document` write-back
and re-read.

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

## Run through the official DataHub MCP server

Install the MCP extra, export your DataHub connection only in the process environment,
then run the read-only command:

```bash
python -m pip install -e '.[mcp]'
export DATAHUB_GMS_URL='https://your-instance.example/gms'
export DATAHUB_GMS_TOKEN='your-token'
datahub-contract-bridge plan-mcp \
  --manifest tests/fixtures/manifest.json \
  --output artifacts/live-plan
```

The adapter launches `mcp-server-datahub` over stdio and requires its official
`search`, `list_schema_fields`, `get_entities`, and `get_lineage` tools. It rejects no
exact match, multiple exact matches, schemas over 1,000 fields, and downstream windows
over 100 assets instead of silently planning with partial context. Mutation tools are
forced off for this command. Tokens and endpoints are never written to plan artifacts.

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
