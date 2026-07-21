# Demonstration video plan

Target length: 2:35. Public YouTube or Vimeo upload; no music and no third-party footage.
Record only the public repository, terminal, generated artifacts, and public workflow.

The rendered 1280×720 MP4 is
`submission/video/datahub-contract-bridge-demo.mp4`. It uses synthetic narration and
hard-coded captions; the six scene sources, narration text, live public-workflow
screenshot and deterministic render script are in `submission/video/`. The fixture
command and all checks must pass immediately before a final render.

Final render record (21 July 2026): 2:35.03, 3.1 MB, SHA-256
`717bfac00581cf500d0018ba0a4e17540839d81e5a1e3891a6abb224b9e3d178`.
The complete file was decoded after rendering; all six frames were visually checked.

## Script and shots

### 0:00–0:18 — Problem

**Screen:** repository title, then `tests/fixtures/manifest.json` beside
`tests/fixtures/catalog.json`.

**Narration:** “dbt knows the contract a model declares. DataHub knows the live schema,
owners, and downstream graph. Contract Bridge joins those views before a change is
allowed to leave a durable record.”

### 0:18–0:48 — Read and plan

**Screen:** run the offline quick-start command, then open `artifacts/demo/plan.md`.

**Narration:** “The agent selects one enforced dbt contract and only explicitly tagged
contract tests. Through the official DataHub MCP server, the live mode resolves exactly
one dataset, paginates its schema, reads owners, and bounds lineage to one hop. The same
pure planner makes the fixture demo reproducible.”

### 0:48–1:18 — Useful output

**Screen:** slowly highlight `TYPE_CHANGE`, `FIELD_REMOVAL`, `DOWNSTREAM_IMPACT`, owner,
and plan hash in the demo Markdown.

**Narration:** “The output separates high-risk removal and type drift from additions,
then names downstream impact and ownership. JSON supports automation; Markdown gives a
reviewer the same facts. The SHA-256 binds this exact plan to any later write.”

### 1:18–1:52 — Guarded action

**Screen:** README `Confirmed write-back` commands, then the confirmation check in the
CLI or test output.

**Narration:** “Read-only is the default. Applying a plan starts a mutation-enabled MCP
session, re-reads live context, recomputes the plan, and refuses a stale or mistyped
hash before writing. The document URN is derived from the hash, so retrying updates the
same record.”

### 1:52–2:20 — Live proof

**Screen:** successful public Actions run 29842906648, then
`examples/verified-live/writeback-receipt.json` and the matching hash in `plan.json`.

**Narration:** “This public run started DataHub OSS 1.5.0.6 with DataHub's synthetic
sample, completed the official MCP read and write, then closed the writer. A fresh
read-only MCP process verified the exact title, length, full content, and an overlapping
read. Only then did it emit verified true.”

### 2:20–2:35 — Close

**Screen:** README safety model and repository test command.

**Narration:** “Contract Bridge does not replace DataHub contracts or impact analysis.
It composes dbt intent, catalog context, human confirmation, and durable verified
write-back into one auditable workflow.”

## Recording checklist

- Use a clean terminal at 1280×720 or higher and font size large enough to read.
- Run the fixture command immediately before recording; do not simulate terminal output.
- Keep the hash and `verified: true` legible, but show no private account page or token.
- Show the successful public workflow URL in the browser address bar.
- Export under 3 minutes and watch the complete final file before upload.
