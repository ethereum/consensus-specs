from pysetup.constants import EIP8025

from .base import BaseSpecBuilder


class EIP8025SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8025

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.gloas import {preset_name} as gloas
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        return {
            "SIGNED_EXECUTION_PAYLOAD_BID_GINDEX": "GeneralizedIndex(357)",
        }

    @classmethod
    def proof_engine_cls(cls) -> str:
        return """
class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofEngine,
                               execution_proof: ExecutionProof,
                               chain_config_root: Root) -> bool:
        return False

    def request_proof(self: ProofEngine,
                      private_input: PrivateInput,
                      proof_type: ProofType,
                      chain_config_root: Root) -> Root:
        raise NotImplementedError("no default proof generation")


PROOF_ENGINE = NoopProofEngine()"""
