"""Materialize aspect-model solutions for Gloas payload attestations."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.payload_attestation import prepare_signed_payload_attestation
from eth_consensus_specs.test.utils.dumper import Dumper

from ...gen_base.gen_typing import TestCase, TestCasePart, TestCaseResult
from ...gen_base.output import dump_test_case_result

if TYPE_CHECKING:
    from pathlib import Path

_DIMS = [
    "parent_root_matches",
    "slot_is_previous",
    "attesting_indices_nonempty",
    "signature_valid",
    "state_effected",
    "outcome",
]


def _s(sol: Any, name: str) -> str:
    return str(getattr(sol, name))


def _b(sol: Any, name: str) -> bool:
    return bool(getattr(sol, name))


class PayloadAttestationMaterializer:
    def __init__(self, spec: Any, model_path: Path, fork_name="gloas", preset_name="minimal"):
        self.spec, self.model_path = spec, model_path
        self.fork_name, self.preset_name = fork_name, preset_name

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        self.spec.process_slots(state, self.spec.Slot(3))
        return state

    def materialize_solution(self, sol: Any) -> tuple[Any, Any, Any | None, dict]:
        spec, pre = self.spec, self._base_state()
        slot = pre.slot - 1 if _b(sol, "slot_is_previous") else pre.slot
        root = (
            pre.latest_block_header.parent_root
            if _b(sol, "parent_root_matches")
            else spec.Root(b"\x42" * 32)
        )
        nonempty = _b(sol, "attesting_indices_nonempty")
        operation = prepare_signed_payload_attestation(
            spec,
            pre,
            slot=slot,
            beacon_block_root=root,
            attesting_indices=None if nonempty else [],
            valid_signature=nonempty and _s(sol, "signature_valid") == "T",
        )
        post = pre.copy()
        try:
            spec.process_payload_attestation(post, operation)
        except (AssertionError, IndexError):
            post = None
        claimed = {
            name: (_b(sol, name) if isinstance(getattr(sol, name), bool) else _s(sol, name))
            for name in _DIMS
        }
        return pre, operation, post, claimed

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, sol: Any) -> None:
        pre, operation, post, claimed = self.materialize_solution(sol)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name,
            preset_name=self.preset_name,
            runner_name="operations",
            handler_name="payload_attestation",
            suite_name="main",
            case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("payload_attestation", "ssz", operation.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        dump_test_case_result(
            TestCaseResult(
                test_case=test_case,
                meta={
                    "description": f"process_payload_attestation: {claimed['outcome']}",
                    "bls_setting": 1,
                },
                case_parts=parts,
            ),
            dumper,
        )
        dumper.dump_data(test_case.dir, "dimensions", {"case": case_name, "claimed": claimed})

    def materialize_reps(self, output_dir: Path, reps: list) -> int:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        dumper = Dumper()
        for index, sol in enumerate(reps):
            self.write_case(dumper, output_dir, index, sol)
        print(f"Generated {len(reps)} test cases in {output_dir}")
        return len(reps)
