"""Enumerated MiniZinc solutions used by withdrawal-processing coverage."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import minizinc

from tests.generators.compliance_runners.state_transition.aspects.base import (
    OpBool,
    OpCmp,
    ValidatorCredentialKind,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder import (
    Builder as BuilderSolution,
    is_self_builder,
    is_sweep_eligible,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal import (
    BuilderPendingWithdrawal,
)
from tests.generators.compliance_runners.state_transition.aspects.validator.validator import (
    Validator,
)
from tests.generators.compliance_runners.state_transition.aspects.validator_withdrawals.pending_partial_withdrawal import (
    ValidatorPendingPartialWithdrawal,
)
from tests.generators.compliance_runners.state_transition.materializer.common import (
    BOOL,
    CMP,
    OP_BOOL,
    OP_CMP,
    to_builder_solution,
)
from tests.generators.compliance_runners.state_transition.withdrawal_processing.models import (
    BUILDER_MODEL,
    PENDING_MODEL,
    PENDING_PARTIAL_WITHDRAWAL_MODEL,
)

_CRED = {
    "BLS": ValidatorCredentialKind.BLS,
    "ETH1": ValidatorCredentialKind.ETH1,
    "COMPOUNDING": ValidatorCredentialKind.COMPOUNDING,
}


@dataclass(frozen=True)
class SolutionCatalog:
    all_builder_solutions: tuple[BuilderSolution, ...]
    all_builder_pending_withdrawal_solutions: tuple[BuilderPendingWithdrawal, ...]
    all_validator_pending_withdrawal_solutions: tuple[ValidatorPendingPartialWithdrawal, ...]
    ref_candidates: tuple[BuilderSolution, ...]
    active_candidates: tuple[BuilderSolution, ...]


@cache
def get_solution_catalog() -> SolutionCatalog:
    """Enumerate and cache all solutions needed to materialize this handler."""
    all_builder_solutions = enumerate_all_builder_solutions(BUILDER_MODEL)
    return SolutionCatalog(
        all_builder_solutions=tuple(all_builder_solutions),
        all_builder_pending_withdrawal_solutions=tuple(
            enumerate_all_pending_withdrawal_solutions(PENDING_MODEL)
        ),
        all_validator_pending_withdrawal_solutions=tuple(
            enumerate_all_validator_pending_withdrawal_solutions(PENDING_PARTIAL_WITHDRAWAL_MODEL)
        ),
        ref_candidates=tuple(
            bs
            for bs in all_builder_solutions
            if not is_self_builder(bs)
            and is_sweep_eligible(bs)
            and bs.has_pending_payments == OpBool.F
            and bs.has_pending_withdrawals == OpBool.F
            and bs.cmp_finalized_epoch_deposit_epoch == OpCmp.GT
        ),
        active_candidates=tuple(
            bs
            for bs in all_builder_solutions
            if not is_self_builder(bs)
            and bs.has_pending_withdrawals == OpBool.T
            and bs.has_pending_payments == OpBool.F
            and bs.payload_builder_version == OpBool.T
        ),
    )


def _to_validator_solution(rec: dict[str, str]) -> Validator:
    return Validator(
        withdrawal_credential=_CRED[rec["withdrawal_credential"]],
        cmp_state_epoch_activation_epoch=CMP[rec["cmp_state_epoch_activation_epoch"]],
        cmp_state_epoch_exit_epoch=CMP[rec["cmp_state_epoch_exit_epoch"]],
        cmp_state_epoch_withdrawal_epoch=CMP[rec["cmp_state_epoch_withdrawal_epoch"]],
        cmp_finalized_epoch_activation_eligibility_epoch=CMP[
            rec["cmp_finalized_epoch_activation_eligibility_epoch"]
        ],
        withdrawable_epoch_set=BOOL[rec["withdrawable_epoch_set"]],
        exit_epoch_set=BOOL[rec["exit_epoch_set"]],
        cmp_balance_zero=CMP[rec["cmp_balance_zero"]],
        cmp_effective_balance_min_activation_balance=CMP[
            rec["cmp_effective_balance_min_activation_balance"]
        ],
        has_pending_withdrawal=BOOL[rec["has_pending_withdrawal"]],
    )


def enumerate_all_builder_solutions(model_path: Path) -> list[BuilderSolution]:
    model = minizinc.Model(str(model_path))
    result = minizinc.Instance(minizinc.Solver.lookup("gecode"), model).solve(all_solutions=True)
    return [
        BuilderSolution(
            payload_builder_version=OP_BOOL[str(sol.b["payload_builder_version"])],
            cmp_state_epoch_deposit_epoch=OP_CMP[str(sol.b["cmp_state_epoch_deposit_epoch"])],
            cmp_state_epoch_withdrawal_epoch=OP_CMP[str(sol.b["cmp_state_epoch_withdrawal_epoch"])],
            cmp_finalized_epoch_deposit_epoch=OP_CMP[
                str(sol.b["cmp_finalized_epoch_deposit_epoch"])
            ],
            withdrawable_epoch_set=OP_BOOL[str(sol.b["withdrawable_epoch_set"])],
            cmp_balance_zero=OP_CMP[str(sol.b["cmp_balance_zero"])],
            cmp_balance_min_deposit=OP_CMP[str(sol.b["cmp_balance_min_deposit"])],
            has_pending_payments=OP_BOOL[str(sol.b["has_pending_payments"])],
            has_pending_withdrawals=OP_BOOL[str(sol.b["has_pending_withdrawals"])],
        )
        for sol in result
    ]


def enumerate_all_pending_withdrawal_solutions(
    model_path: Path,
) -> list[BuilderPendingWithdrawal]:
    model = minizinc.Model(str(model_path))
    result = minizinc.Instance(minizinc.Solver.lookup("gecode"), model).solve(all_solutions=True)
    return [
        BuilderPendingWithdrawal(
            builder=to_builder_solution(
                {k: str(v) for k, v in sol.p["pending_withdrawal"]["builder"].items()}
            ),
            cmp_pending_amount_zero=OP_CMP[
                str(sol.p["pending_withdrawal"]["cmp_pending_amount_zero"])
            ],
            cmp_builder_balance_amount=OP_CMP[
                str(sol.p["pending_withdrawal"]["cmp_builder_balance_amount"])
            ],
        )
        for sol in result
    ]


def enumerate_all_validator_pending_withdrawal_solutions(
    model_path: Path,
) -> list[ValidatorPendingPartialWithdrawal]:
    model = minizinc.Model(str(model_path))
    result = minizinc.Instance(minizinc.Solver.lookup("gecode"), model).solve(all_solutions=True)
    return [
        ValidatorPendingPartialWithdrawal(
            validator=_to_validator_solution({k: str(v) for k, v in sol.w["validator"].items()}),
            withdrawable=BOOL[str(sol.w["withdrawable"])],
            cmp_pending_amount_zero=CMP[str(sol.w["cmp_pending_amount_zero"])],
            cmp_balance_amount=CMP[str(sol.w["cmp_balance_amount"])],
        )
        for sol in result
    ]
