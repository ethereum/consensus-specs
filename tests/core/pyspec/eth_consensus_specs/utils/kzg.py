"""
KZG utilities backed by the c-kzg-4844 library.
"""

import json
import tempfile
from pathlib import Path

import ckzg

trusted_setup = None


def _find_trusted_setup_path() -> Path:
    """
    Locate the trusted setup JSON by walking up from this file to the repo root.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "presets" / "mainnet" / "trusted_setups" / "trusted_setup_4096.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("could not locate trusted setup")


def load_trusted_setup(precompute: int = 0):
    """
    Load and cache the trusted setup. The JSON file (with g1_monomial,
    g1_lagrange, g2_monomial hex arrays) is converted to the text format that
    ckzg.load_trusted_setup expects.
    """
    global trusted_setup
    if trusted_setup is not None:
        return trusted_setup

    with _find_trusted_setup_path().open() as f:
        data = json.load(f)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as tf:
        tf.write(f"{len(data['g1_lagrange'])}\n")
        tf.write(f"{len(data['g2_monomial'])}\n")
        for point in data["g1_lagrange"]:
            tf.write(point[2:] + "\n")
        for point in data["g2_monomial"]:
            tf.write(point[2:] + "\n")
        for point in data["g1_monomial"]:
            tf.write(point[2:] + "\n")
        txt_path = tf.name
        tf.flush()

        trusted_setup = ckzg.load_trusted_setup(txt_path, precompute)

    return trusted_setup


def blob_to_kzg_commitment(blob):
    try:
        return ckzg.blob_to_kzg_commitment(bytes(blob), trusted_setup)
    except Exception as e:
        raise AssertionError(str(e)) from e


def compute_blob_kzg_proof(blob, commitment_bytes):
    try:
        return ckzg.compute_blob_kzg_proof(bytes(blob), bytes(commitment_bytes), trusted_setup)
    except Exception as e:
        raise AssertionError(str(e)) from e


def verify_blob_kzg_proof(blob, commitment_bytes, proof_bytes):
    try:
        return ckzg.verify_blob_kzg_proof(
            bytes(blob),
            bytes(commitment_bytes),
            bytes(proof_bytes),
            trusted_setup,
        )
    except Exception as e:
        raise AssertionError(str(e)) from e


def verify_blob_kzg_proof_batch(blobs, commitments_bytes, proofs_bytes):
    try:
        return ckzg.verify_blob_kzg_proof_batch(
            b"".join(bytes(blob) for blob in blobs),
            b"".join(bytes(commitment) for commitment in commitments_bytes),
            b"".join(bytes(proof) for proof in proofs_bytes),
            trusted_setup,
        )
    except Exception as e:
        raise AssertionError(str(e)) from e


def compute_cells(blob):
    try:
        return ckzg.compute_cells(bytes(blob), trusted_setup)
    except Exception as e:
        raise AssertionError(str(e)) from e


def compute_cells_and_kzg_proofs(blob):
    try:
        return ckzg.compute_cells_and_kzg_proofs(bytes(blob), trusted_setup)
    except Exception as e:
        raise AssertionError(str(e)) from e


def verify_cell_kzg_proof_batch(commitments_bytes, cell_indices, cells, proofs_bytes):
    try:
        return ckzg.verify_cell_kzg_proof_batch(
            [bytes(commitment) for commitment in commitments_bytes],
            [int(cell_index) for cell_index in cell_indices],
            [bytes(cell) for cell in cells],
            [bytes(proof) for proof in proofs_bytes],
            trusted_setup,
        )
    except Exception as e:
        raise AssertionError(str(e)) from e


def recover_cells_and_kzg_proofs(cell_indices, cells):
    try:
        return ckzg.recover_cells_and_kzg_proofs(
            [int(cell_index) for cell_index in cell_indices],
            [bytes(cell) for cell in cells],
            trusted_setup,
        )
    except Exception as e:
        raise AssertionError(str(e)) from e
