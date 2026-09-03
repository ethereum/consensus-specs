"""Shared helpers and base class for state-transition materializers."""

from __future__ import annotations

import shutil
from datetime import timedelta
from typing import Any, TYPE_CHECKING

import minizinc

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.utils.dumper import Dumper
from tests.generators.compliance_runners.gen_base.gen_typing import TestCase, TestCaseResult
from tests.generators.compliance_runners.gen_base.output import dump_test_case_result
from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    OpBool,
    OpCmp,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder import (
    Builder as BuilderSolution,
)
from tests.generators.compliance_runners.state_transition.materializer.state_preprocessor import (
    common_state_preprocessor,
)

if TYPE_CHECKING:
    from pathlib import Path

BIG = 10_000_000_000  # 10 Gwei, well above MIN_DEPOSIT_AMOUNT

BOOL = {"F": Bool.F, "T": Bool.T}
CMP = {"LT": Cmp.LT, "EQ": Cmp.EQ, "GT": Cmp.GT}
OP_CMP = {"LT": OpCmp.LT, "EQ": OpCmp.EQ, "GT": OpCmp.GT, "NA_CMP": OpCmp.NA}
OP_BOOL = {"F": OpBool.F, "T": OpBool.T, "NA_BOOL": OpBool.NA}


def to_builder_solution(rec: dict[str, Any]) -> BuilderSolution:
    """Build a Builder solution from a flat {dim: string} record."""
    return BuilderSolution(
        payload_builder_version=OP_BOOL[rec["payload_builder_version"]],
        cmp_state_epoch_deposit_epoch=OP_CMP[rec["cmp_state_epoch_deposit_epoch"]],
        cmp_state_epoch_withdrawal_epoch=OP_CMP[rec["cmp_state_epoch_withdrawal_epoch"]],
        cmp_finalized_epoch_deposit_epoch=OP_CMP[rec["cmp_finalized_epoch_deposit_epoch"]],
        withdrawable_epoch_set=OP_BOOL[rec["withdrawable_epoch_set"]],
        cmp_balance_zero=OP_CMP[rec["cmp_balance_zero"]],
        cmp_balance_min_deposit=OP_CMP[rec["cmp_balance_min_deposit"]],
        has_pending_payments=OP_BOOL[rec["has_pending_payments"]],
        has_pending_withdrawals=OP_BOOL[rec["has_pending_withdrawals"]],
    )


def set_parent_block(spec: Any, state: Any, hash_match: str) -> None:
    """Set the parent-block state per state_latest_block_hash_match."""
    if hash_match == "T":
        # Parent block full: hashes must match (use a non-zero hash)
        if bytes(state.latest_block_hash) == b"\x00" * 32:
            state.latest_block_hash = spec.Hash32(b"\x01" * 32)
        state.latest_execution_payload_bid.block_hash = state.latest_block_hash
    else:
        # Parent block empty: hashes must differ
        state.latest_block_hash = spec.Hash32(b"\x00" * 32)
        state.latest_execution_payload_bid.block_hash = spec.Hash32(b"\x01" * 32)


def make_base_state(spec: Any, num_validators: int = 64, preprocess: bool = True) -> Any:
    """Build a preprocessed base state (genesis + optional 2-epoch advance)."""
    state = create_genesis_state(
        spec,
        validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * num_validators,
        activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
    )
    state.builders = type(state.builders)()
    state.builder_pending_payments = type(state.builder_pending_payments)()
    state.builder_pending_withdrawals = type(state.builder_pending_withdrawals)()
    if preprocess:
        state = common_state_preprocessor(spec, state)
    return state


class BaseMaterializer:
    """Shared solving + test-case emission for state-transition materializers.

    Subclasses set `handler_name`, `description`, `validator_name`, and
    `bls_setting` (class attributes) and implement `materialize_solution`, which
    must return ``(pre, post, verified, claimed, extra_parts)`` where
    `extra_parts` is a list of ``(name, ssz_object)`` case parts inserted
    between ``pre`` and ``post``.
    """

    handler_name = "withdrawals"
    description = "case"
    validator_name = "validator"
    bls_setting = 0

    def __init__(self, spec: Any, model_path: Path, fork_name="gloas", preset_name="minimal"):
        self.spec = spec
        self.model_path = model_path
        self.fork_name = fork_name
        self.preset_name = preset_name

    def materialize_solution(self, sol: Any) -> tuple[Any, Any | None, bool, dict, list]:
        raise NotImplementedError

    def describe(self, claimed: dict) -> str:
        return f"{self.description}: {claimed}"

    def case_parts(self, pre: Any, post: Any | None, extra_parts: list) -> list:
        parts = [("pre", "ssz", pre.encode_bytes())]
        for name, obj in extra_parts:
            parts.append((name, "ssz", obj.encode_bytes()))
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return parts

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, sol: Any) -> bool:
        pre, post, verified, claimed, extra_parts = self.materialize_solution(sol)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name,
            preset_name=self.preset_name,
            runner_name="operations",
            handler_name=self.handler_name,
            suite_name="main",
            case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        meta = {"description": self.describe(claimed), "verified": verified}
        if self.bls_setting:
            meta["bls_setting"] = self.bls_setting
        dump_test_case_result(
            TestCaseResult(
                test_case=test_case,
                meta=meta,
                case_parts=self.case_parts(pre, post, extra_parts),
            ),
            dumper,
        )
        dumper.dump_data(test_case.dir, "dimensions", {"case": case_name, "claimed": claimed})
        return verified

    def materialize_reps(self, output_dir: Path, reps: list) -> tuple[int, int]:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dumper = Dumper()
        verified_count = 0
        for i, sol in enumerate(reps):
            if self.write_case(dumper, output_dir, i, sol):
                verified_count += 1
        print(
            f"Generated {len(reps)} test cases in {output_dir} "
            f"({verified_count}/{len(reps)} verified by {self.validator_name})"
        )
        return len(reps), verified_count

    def materialize_all(self, output_dir: Path, timeout_s: int = 300) -> tuple[int, int]:
        model = minizinc.Model(str(self.model_path))
        result = minizinc.Instance(
            minizinc.Solver.lookup("gecode"),
            model,
        ).solve(all_solutions=True, timeout=timedelta(seconds=timeout_s))
        reps = list(result)
        return self.materialize_reps(output_dir, reps)
