"""Extract per-vector attributes independently of coverage declarations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    body = ctx.operation
    return {
        "deposits": len(body.deposits),
        "proposer_slashings": len(body.proposer_slashings),
        "attester_slashings": len(body.attester_slashings),
        "attestations": len(body.attestations),
        "voluntary_exits": len(body.voluntary_exits),
        "bls_to_execution_changes": len(body.bls_to_execution_changes),
        "payload_attestations": len(body.payload_attestations),
    }
