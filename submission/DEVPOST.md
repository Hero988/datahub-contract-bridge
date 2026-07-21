# Devpost submission draft

## Project name

DataHub Contract Bridge

## Tagline

Turn dbt contract intent into a lineage-aware DataHub review, then write back only the
exact plan a human approved.

## Challenge

Primary: Agents That Do Real Work

## Project URL and source

<https://github.com/Hero988/datahub-contract-bridge>

## Demo video

<https://youtu.be/g-hDNGLs8eY>

## Inspiration

dbt knows what a model declares. DataHub knows what already exists, who owns it, and
what depends on it. Teams still have to reconcile those two views before a schema or
contract change is safe. DataHub issue #11927 describes a real user's custom mapping
between dbt contracts and DataHub contracts, while DataHub's native contract feature is
still evolving. Contract Bridge makes that review explicit, reproducible, and guarded.

## What it does

Contract Bridge is a deterministic data-contract agent. It:

1. reads one enforced model contract plus explicitly `contract`-tagged tests from a dbt
   `manifest.json`;
2. launches DataHub's official MCP server and resolves exactly one matching dataset;
3. reads the current schema, owners, and bounded one-hop downstream lineage;
4. classifies additions, removals, type drift, missing ownership, and downstream
   impact;
5. emits a human-readable Markdown review and machine-readable JSON plan with a stable
   SHA-256; and
6. writes the review back to one deterministic DataHub document only when the operator
   supplies that exact hash, then verifies the write from a fresh read-only MCP session.

The default MCP command cannot mutate. Ambiguous assets, incomplete pagination, stale
hashes, oversized documents, unexpected response shapes, and failed re-reads all stop
the workflow rather than producing a success claim.

## How we built it

The project is a Python 3.11+ CLI with no runtime dependency for fixture planning. Its
live extra uses DataHub's official `mcp-server-datahub` over stdio. The same pure planner
operates on deterministic fixtures and live MCP context, which keeps comparison logic
testable without pretending fixtures are integration tests.

The live proof runs DataHub OSS 1.5.0.6 on a disposable GitHub-hosted runner, ingests
only DataHub's official `SampleHiveDataset`, executes the read/plan/confirm/write/re-read
flow, checks `verified: true`, byte-compares the plans from the read and write sessions,
and preserves non-secret artifacts. Successful run:
<https://github.com/Hero988/datahub-contract-bridge/actions/runs/29842906648>.

## What makes it original

DataHub already provides contracts, lineage, impact analysis, and MCP tools. Contract
Bridge does not rebuild them. It composes four operations that are otherwise separate:
dbt contract/test compilation, exact catalog resolution, lineage-and-owner-aware risk
review, and hash-confirmed durable write-back. The confirmation hash binds the reviewed
artifact to the later mutation session, and the deterministic document URN makes retries
idempotent.

## Challenges we ran into

The official MCP server chooses its document-tool surface at process startup, so a
fresh read-only process is required after mutation. Its `get_entities` response also
uses a union-shaped transport that exposes only a URN in structured content. Rather
than infer success, Contract Bridge switched verification to the official
`grep_documents` raw-content path and checks the full content through two overlapping
reads. DataHub's search index can converge after ingestion, so live lookup retries are
bounded and preserve exact matching.

## Accomplishments

- Twelve deterministic tests cover manifest selection, exact MCP reads, pagination,
  fail-closed conditions, confirmation, deterministic URNs, and verified write-back.
- The public live workflow completed the exact read, guarded write, and fresh-session
  re-read against DataHub OSS.
- Sample JSON and Markdown outputs are committed for evaluation without setup.
- No production endpoint, customer metadata, or secret enters the artifacts.

## What we learned

For catalog agents, write access is the easy part; proving that the reviewed context and
the written result are exactly the same is the real safety boundary. Stable hashes,
bounded reads, deterministic identifiers, and independent verification turn a useful
automation into an auditable one.

## What's next

The next safe extension is a pull-request check that publishes the plan for review and
passes its exact hash to a separately authorized write job. Broader contract mutation
will remain preview-only until DataHub exposes a stable supported contract-write API
with equivalent re-read guarantees.

## Technologies and data

Python, pytest, Ruff, DataHub OSS 1.5.0.6, DataHub's official MCP server, dbt manifest
artifacts, GitHub Actions, and DataHub's official synthetic `SampleHiveDataset`.

## Testing instructions

The repository README starts with a no-credential fixture demo. Judges can inspect the
preserved live plan and verified receipt in `examples/verified-live/`, and can reproduce
the full live path by manually dispatching the public workflow. The workflow installs
its own DataHub OSS instance and uses only synthetic sample data.

## Honest scope note

The project writes a review document back to DataHub. It does not claim to apply a
native DataHub contract, change a production schema, or prove production readiness.
