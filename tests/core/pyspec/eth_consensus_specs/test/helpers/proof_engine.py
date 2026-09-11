class MockProofEngine:
    def __init__(self, *, valid_proof_data=None, proof=None):
        self.valid_proof_data = valid_proof_data
        self.proof = proof
        self.verifications = []
        self.requests = []
        self.retrievals = []

    def verify_execution_proof(self, proof):
        self.verifications.append(proof)
        return self.valid_proof_data is None or proof.proof_data in self.valid_proof_data

    def request_proofs(self, new_payload_request, chain_id, schema_id, proof_attributes):
        self.requests.append((new_payload_request, chain_id, schema_id, proof_attributes))
        return new_payload_request.hash_tree_root()

    def get_proof(self, new_payload_request_root, proof_type):
        self.retrievals.append((new_payload_request_root, proof_type))
        return self.proof
