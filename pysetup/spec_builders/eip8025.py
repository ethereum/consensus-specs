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
    "stateless": {
        "tag": "eip8025-experimental",
        "status": "experimental",
    },
}
"""

    @classmethod
    def proof_engine_cls(cls) -> str:
        return """
class ProofEngine(ProofVerifier, ProofGenerator, Protocol):
    pass


class NoopProofVerifier(ProofVerifier):

    def verify_execution_proof(self: ProofVerifier,
                               execution_proof: ExecutionProof,
                               chain_config_root: Root) -> bool:
        return False


class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofVerifier,
                               execution_proof: ExecutionProof,
                               chain_config_root: Root) -> bool:
        return False

    def request_proof(self: ProofGenerator,
                      private_input: PrivateInput,
                      proof_type: ProofType,
                      chain_config_root: Root) -> Root:
        raise NotImplementedError("no default proof generation")


PROOF_VERIFIER = NoopProofVerifier()
PROOF_ENGINE = NoopProofEngine()"""
