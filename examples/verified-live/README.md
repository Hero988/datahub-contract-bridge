# Verified live DataHub evidence

These files were downloaded unchanged from the successful public GitHub Actions run
[29842906648](https://github.com/Hero988/datahub-contract-bridge/actions/runs/29842906648).
The job used DataHub OSS 1.5.0.6, DataHub's official synthetic `SampleHiveDataset`, and
the official DataHub MCP server on a disposable runner.

The evidence chain is:

1. `plan.json` records the exact live schema and owners returned through MCP, the dbt
   contract intent, classified risks, and plan SHA-256.
2. `plan.md` is the reviewable rendering produced from that same plan.
3. `writeback-receipt.json` records the deterministic DataHub document URN and confirms
   `"verified": true` after a fresh read-only MCP process re-read the exact title,
   content length, complete content, and an overlapping content window.
4. The workflow also byte-compared the pre-write and write-session plan JSON files.

The workflow definition is
[`live-datahub-integration.yml`](../../.github/workflows/live-datahub-integration.yml).
It is manual-only, concurrency-limited, capped at 45 minutes, uses no private data, and
uploads only these non-secret artifacts.

This directory is evidence of one specific synthetic integration run. It is not a
benchmark, production deployment, or claim that a customer's contract was applied.
