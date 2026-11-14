from pysetup.constants import EIP8440

from .base import BaseSpecBuilder


class EIP8440SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8440

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.eip8025 import {preset_name} as eip8025
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return {
            "MAX_SIGNED_EXECUTION_PROOF_ENVELOPE_SIZE",
        }

    @classmethod
    def deprecate_containers(cls) -> set[str]:
        return {
            "ExecutionProofEnvelope",
            "SignedExecutionProofEnvelope",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "get_execution_proof",
            "verify_execution_proof_envelope",
        }
