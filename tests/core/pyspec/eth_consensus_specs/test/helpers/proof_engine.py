from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root


class MockProofEngine:
    def __init__(self, *, verification_result=True, proof=None):
        self.verification_result = verification_result
        self.proof = proof
        self.verifications = []
        self.requests = []
        self.retrievals = []

    def verify_execution_proof(self, proof):
        self.verifications.append(proof)
        return self.verification_result

    def request_proofs(self, new_payload_request, chain_id, schema_id, proof_attributes):
        self.requests.append((new_payload_request, chain_id, schema_id, proof_attributes))
        return hash_tree_root(new_payload_request)

    def get_proof(self, new_payload_request_root, proof_type):
        self.retrievals.append((new_payload_request_root, proof_type))
        return self.proof
