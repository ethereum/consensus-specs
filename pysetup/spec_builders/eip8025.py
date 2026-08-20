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
    def preparations(cls) -> str:
        return """
EIP8025_FEATURES = {
    "prover": {
        "tag": "eip8025-prover",
        "status": "optional",
    },
}
"""

    @classmethod
    def proof_engine_cls(cls) -> str:
        return """
class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofEngine,
                               execution_proof: ExecutionProof) -> bool:
        return False

    def request_proofs(self: ProofEngine,
                       beacon_block_root: Root,
                       proof_attributes: ProofAttributes) -> Root:
        raise NotImplementedError("no default proof generation")

    def get_proof(self: ProofEngine,
                  beacon_block_root: Root,
                  proof_type: ProofType) -> ExecutionProof:
        raise NotImplementedError("no default proof retrieval")


PROOF_ENGINE = NoopProofEngine()"""
