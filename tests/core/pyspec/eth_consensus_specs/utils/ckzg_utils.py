import json
import os
import tempfile

import ckzg

# Cache loaded trusted setups by file path.
_trusted_setup_cache: dict[str, object] = {}


def load_trusted_setup(json_path: str, precompute: int = 0) -> object:
    """
    Load a trusted setup from a JSON file (with g1_monomial, g1_lagrange,
    g2_monomial hex arrays) by converting it to the text format that ckzg
    expects, then calling ckzg.load_trusted_setup.
    """
    abs_path = os.path.abspath(json_path)
    cache_key = (abs_path, precompute)
    if cache_key in _trusted_setup_cache:
        return _trusted_setup_cache[cache_key]

    with open(abs_path) as f:
        data = json.load(f)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        tf.write(f"{len(data['g1_lagrange'])}\n")
        tf.write(f"{len(data['g2_monomial'])}\n")
        for point in data["g1_lagrange"]:
            tf.write(point[2:] + "\n")
        for point in data["g2_monomial"]:
            tf.write(point[2:] + "\n")
        for point in data["g1_monomial"]:
            tf.write(point[2:] + "\n")
        txt_path = tf.name

    try:
        ts = ckzg.load_trusted_setup(txt_path, precompute)
    finally:
        os.unlink(txt_path)

    _trusted_setup_cache[cache_key] = ts
    return ts


def apply_ckzg_to_spec(spec, ts):
    """
    Monkey-patch the KZG functions on a spec module to use ckzg wrappers.
    Only patches functions that exist on the module.
    """
    # --- Deneb functions ---

    if hasattr(spec, "blob_to_kzg_commitment"):

        def blob_to_kzg_commitment(blob):
            try:
                result = ckzg.blob_to_kzg_commitment(bytes(blob), ts)
            except Exception as e:
                raise AssertionError(str(e)) from e
            return spec.KZGCommitment(result)

        spec.blob_to_kzg_commitment = blob_to_kzg_commitment

    if hasattr(spec, "compute_kzg_proof"):

        def compute_kzg_proof(blob, z_bytes):
            try:
                proof, y = ckzg.compute_kzg_proof(bytes(blob), bytes(z_bytes), ts)
            except Exception as e:
                raise AssertionError(str(e)) from e
            return spec.KZGProof(proof), spec.Bytes32(y)

        spec.compute_kzg_proof = compute_kzg_proof

    if hasattr(spec, "compute_blob_kzg_proof"):

        def compute_blob_kzg_proof(blob, commitment_bytes):
            try:
                result = ckzg.compute_blob_kzg_proof(bytes(blob), bytes(commitment_bytes), ts)
            except Exception as e:
                raise AssertionError(str(e)) from e
            return spec.KZGProof(result)

        spec.compute_blob_kzg_proof = compute_blob_kzg_proof

    if hasattr(spec, "verify_kzg_proof"):

        def verify_kzg_proof(commitment_bytes, z_bytes, y_bytes, proof_bytes):
            try:
                return ckzg.verify_kzg_proof(
                    bytes(commitment_bytes),
                    bytes(z_bytes),
                    bytes(y_bytes),
                    bytes(proof_bytes),
                    ts,
                )
            except Exception as e:
                raise AssertionError(str(e)) from e

        spec.verify_kzg_proof = verify_kzg_proof

    if hasattr(spec, "verify_blob_kzg_proof"):

        def verify_blob_kzg_proof(blob, commitment_bytes, proof_bytes):
            try:
                return ckzg.verify_blob_kzg_proof(
                    bytes(blob), bytes(commitment_bytes), bytes(proof_bytes), ts
                )
            except Exception as e:
                raise AssertionError(str(e)) from e

        spec.verify_blob_kzg_proof = verify_blob_kzg_proof

    if hasattr(spec, "verify_blob_kzg_proof_batch"):

        def verify_blob_kzg_proof_batch(blobs, commitments_bytes, proofs_bytes):
            try:
                return ckzg.verify_blob_kzg_proof_batch(
                    b"".join(bytes(b) for b in blobs),
                    b"".join(bytes(c) for c in commitments_bytes),
                    b"".join(bytes(p) for p in proofs_bytes),
                    ts,
                )
            except Exception as e:
                raise AssertionError(str(e)) from e

        spec.verify_blob_kzg_proof_batch = verify_blob_kzg_proof_batch

    # --- Fulu functions ---

    if hasattr(spec, "compute_cells"):

        def compute_cells(blob):
            try:
                cells = ckzg.compute_cells(bytes(blob), ts)
            except Exception as e:
                raise AssertionError(str(e)) from e
            return [spec.Cell(c) for c in cells]

        spec.compute_cells = compute_cells

    if hasattr(spec, "compute_cells_and_kzg_proofs"):

        def compute_cells_and_kzg_proofs(blob):
            try:
                cells, proofs = ckzg.compute_cells_and_kzg_proofs(bytes(blob), ts)
            except Exception as e:
                raise AssertionError(str(e)) from e
            return (
                [spec.Cell(c) for c in cells],
                [spec.KZGProof(p) for p in proofs],
            )

        spec.compute_cells_and_kzg_proofs = compute_cells_and_kzg_proofs

    if hasattr(spec, "verify_cell_kzg_proof_batch"):

        def verify_cell_kzg_proof_batch(commitments_bytes, cell_indices, cells, proofs_bytes):
            try:
                return ckzg.verify_cell_kzg_proof_batch(
                    [bytes(c) for c in commitments_bytes],
                    [int(i) for i in cell_indices],
                    [bytes(c) for c in cells],
                    [bytes(p) for p in proofs_bytes],
                    ts,
                )
            except Exception as e:
                raise AssertionError(str(e)) from e

        spec.verify_cell_kzg_proof_batch = verify_cell_kzg_proof_batch

    if hasattr(spec, "recover_cells_and_kzg_proofs"):

        def recover_cells_and_kzg_proofs(cell_indices, cells):
            try:
                result_cells, result_proofs = ckzg.recover_cells_and_kzg_proofs(
                    [int(i) for i in cell_indices],
                    [bytes(c) for c in cells],
                    ts,
                )
            except Exception as e:
                raise AssertionError(str(e)) from e
            return (
                [spec.Cell(c) for c in result_cells],
                [spec.KZGProof(p) for p in result_proofs],
            )

        spec.recover_cells_and_kzg_proofs = recover_cells_and_kzg_proofs
