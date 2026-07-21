"""Create deterministic, reviewable plans from dbt intent and DataHub context."""

from __future__ import annotations

import hashlib
import json

from .domain import CatalogContext, ChangePlan, DbtContract, Risk


def _normalise_type(value: str | None) -> str | None:
    if value is None:
        return None
    aliases = {
        "character varying": "varchar",
        "int": "integer",
        "int4": "integer",
        "int8": "bigint",
        "bool": "boolean",
    }
    clean = " ".join(value.strip().lower().split())
    return aliases.get(clean, clean)


def _risk_payload(contract: DbtContract, catalog: CatalogContext) -> tuple[Risk, ...]:
    desired = {field.name.lower(): field for field in contract.fields}
    current = {field.name.lower(): field for field in catalog.fields}
    risks: list[Risk] = []

    for name in sorted(current.keys() - desired.keys()):
        field = current[name]
        risks.append(
            Risk(
                "high",
                "FIELD_REMOVAL",
                field.name,
                "Present in DataHub but absent from the enforced dbt contract.",
            )
        )
    for name in sorted(desired.keys() - current.keys()):
        field = desired[name]
        risks.append(
            Risk(
                "info",
                "FIELD_ADDITION",
                field.name,
                "Declared by dbt but not present in the current DataHub schema.",
            )
        )
    for name in sorted(desired.keys() & current.keys()):
        wanted = _normalise_type(desired[name].data_type)
        actual = _normalise_type(current[name].data_type)
        if wanted and actual and wanted != actual:
            risks.append(
                Risk(
                    "high",
                    "TYPE_CHANGE",
                    desired[name].name,
                    f"dbt declares {wanted}; DataHub currently reports {actual}.",
                )
            )

    if catalog.downstream:
        risks.append(
            Risk(
                "medium",
                "DOWNSTREAM_IMPACT",
                catalog.dataset_urn,
                f"DataHub reports {len(catalog.downstream)} downstream asset(s) "
                "within the requested lineage window.",
            )
        )
    if not catalog.owners:
        risks.append(
            Risk(
                "medium",
                "MISSING_OWNER",
                catalog.dataset_urn,
                "No owner was returned for review routing.",
            )
        )
    if not risks:
        risks.append(
            Risk(
                "info",
                "NO_DIFF",
                catalog.dataset_urn,
                "dbt and DataHub schemas match for compared fields.",
            )
        )
    return tuple(risks)


def build_change_plan(contract: DbtContract, catalog: CatalogContext) -> ChangePlan:
    """Build a stable plan whose hash can be used as a mutation confirmation token."""

    risks = _risk_payload(contract, catalog)
    canonical = {
        "contract": contract,
        "catalog": catalog,
        "risks": risks,
    }
    encoded = json.dumps(
        canonical, default=lambda value: value.__dict__, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return ChangePlan(contract, catalog, risks, digest)


def render_markdown(plan: ChangePlan) -> str:
    """Render a compact artifact that a reviewer can understand without running code."""

    lines = [
        f"# Contract plan: `{plan.contract.relation_name}`",
        "",
        f"- DataHub asset: `{plan.catalog.dataset_urn}`",
        f"- Plan SHA-256: `{plan.plan_sha256}`",
        f"- Declared fields: {len(plan.contract.fields)}",
        f"- Contract-tagged tests: {len(plan.contract.tests)}",
        f"- Downstream assets: {len(plan.catalog.downstream)}",
        f"- Owners: {', '.join(plan.catalog.owners) if plan.catalog.owners else 'none returned'}",
        "",
        "## Risks",
        "",
        "| Severity | Code | Subject | Detail |",
        "|---|---|---|---|",
    ]
    for risk in plan.risks:
        lines.append(f"| {risk.severity} | {risk.code} | `{risk.subject}` | {risk.detail} |")
    lines.extend(
        [
            "",
            "Mutation is not authorized by this artifact. Re-supply the exact "
            "plan hash to confirm write-back.",
            "",
        ]
    )
    return "\n".join(lines)
