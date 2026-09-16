class MockProofEngine:
    def __init__(self, *, valid_proof_data=None):
        self.valid_proof_data = valid_proof_data
        self.verifications = []

    def verify_execution_proof(self, proof):
        self.verifications.append(proof)
        return self.valid_proof_data is None or proof.proof_data in self.valid_proof_data
