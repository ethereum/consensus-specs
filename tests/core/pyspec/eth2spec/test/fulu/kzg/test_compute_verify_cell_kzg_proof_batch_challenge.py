from eth_utils import encode_hex

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import FULU
from eth2spec.test.utils.kzg_tests import (
    encode_hex_list,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest


def _run_compute_verify_cell_kzg_proof_batch_challenge_test(
    spec, commitments, commitment_indices, cell_indices, cosets_evals, proofs, valid: bool = True
):
    if valid:
        challenge = spec.compute_verify_cell_kzg_proof_batch_challenge(
            commitments, commitment_indices, cell_indices, cosets_evals, proofs
        )
    else:
        try:
            challenge = spec.compute_verify_cell_kzg_proof_batch_challenge(
                commitments, commitment_indices, cell_indices, cosets_evals, proofs
            )
            assert False, "should raise exception"
        except Exception:
            pass

    yield (
        "data",
        "data",
        {
            "input": {
                "commitments": encode_hex_list(commitments),
                "commitment_indices": commitment_indices,
                "cell_indices": cell_indices,
                "cosets_evals": [
                    [encode_hex(spec.bls_field_to_bytes(eval)) for eval in coset_evals]
                    for coset_evals in cosets_evals
                ],
                "proofs": encode_hex_list(proofs),
            },
            "output": encode_hex(spec.bls_field_to_bytes(challenge)) if valid else None,
        },
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_empty(spec):
    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        [],
        [],
        [],
        [],
        [],
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_single_cell(spec):
    blob = VALID_BLOBS[0]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    commitments = [commitment]
    commitment_indices = [0]
    cell_indices = [0]
    cosets_evals = [spec.cell_to_coset_evals(cells[0])]
    proofs_selected = [proofs[0]]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_multiple_cells_single_blob(spec):
    blob = VALID_BLOBS[1]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    num_cells = 4
    commitments = [commitment]
    commitment_indices = [0] * num_cells
    cell_indices = list(range(num_cells))
    cosets_evals = [spec.cell_to_coset_evals(cells[i]) for i in range(num_cells)]
    proofs_selected = [proofs[i] for i in range(num_cells)]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_multiple_cells_multiple_blobs(spec):
    blob0 = VALID_BLOBS[2]
    blob1 = VALID_BLOBS[3]
    cells0, proofs0 = spec.compute_cells_and_kzg_proofs(blob0)
    cells1, proofs1 = spec.compute_cells_and_kzg_proofs(blob1)
    commitment0 = spec.blob_to_kzg_commitment(blob0)
    commitment1 = spec.blob_to_kzg_commitment(blob1)

    commitments = [commitment0, commitment1]
    commitment_indices = [0, 1, 0, 1]
    cell_indices = [0, 1, 2, 3]
    cosets_evals = [
        spec.cell_to_coset_evals(cells0[0]),
        spec.cell_to_coset_evals(cells1[1]),
        spec.cell_to_coset_evals(cells0[2]),
        spec.cell_to_coset_evals(cells1[3]),
    ]
    proofs_selected = [proofs0[0], proofs1[1], proofs0[2], proofs1[3]]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_duplicate_cells(spec):
    blob = VALID_BLOBS[4]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    num_duplicates = 3
    commitments = [commitment]
    commitment_indices = [0] * num_duplicates
    cell_indices = [5] * num_duplicates  # Same cell index repeated
    cosets_evals = [spec.cell_to_coset_evals(cells[5])] * num_duplicates
    proofs_selected = [proofs[5]] * num_duplicates

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_many_cells(spec):
    blob = VALID_BLOBS[5]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    # Use half of all cells
    num_cells = spec.CELLS_PER_EXT_BLOB // 2
    commitments = [commitment]
    commitment_indices = [0] * num_cells
    cell_indices = list(range(num_cells))
    cosets_evals = [spec.cell_to_coset_evals(cells[i]) for i in range(num_cells)]
    proofs_selected = [proofs[i] for i in range(num_cells)]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_non_sequential_indices(spec):
    blob = VALID_BLOBS[6]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    # Use non-sequential indices
    indices = [10, 5, 20, 15, 0, 30]
    commitments = [commitment]
    commitment_indices = [0] * len(indices)
    cell_indices = indices
    cosets_evals = [spec.cell_to_coset_evals(cells[i]) for i in indices]
    proofs_selected = [proofs[i] for i in indices]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_mixed_commitment_indices(spec):
    blob0 = VALID_BLOBS[0]
    blob1 = VALID_BLOBS[1]
    blob2 = VALID_BLOBS[2]
    cells0, proofs0 = spec.compute_cells_and_kzg_proofs(blob0)
    cells1, proofs1 = spec.compute_cells_and_kzg_proofs(blob1)
    cells2, proofs2 = spec.compute_cells_and_kzg_proofs(blob2)
    commitment0 = spec.blob_to_kzg_commitment(blob0)
    commitment1 = spec.blob_to_kzg_commitment(blob1)
    commitment2 = spec.blob_to_kzg_commitment(blob2)

    # Mix up the order of commitment indices
    commitments = [commitment0, commitment1, commitment2]
    commitment_indices = [2, 0, 1, 0, 2, 1]
    cell_indices = [0, 1, 2, 3, 4, 5]
    cosets_evals = [
        spec.cell_to_coset_evals(cells2[0]),
        spec.cell_to_coset_evals(cells0[1]),
        spec.cell_to_coset_evals(cells1[2]),
        spec.cell_to_coset_evals(cells0[3]),
        spec.cell_to_coset_evals(cells2[4]),
        spec.cell_to_coset_evals(cells1[5]),
    ]
    proofs_selected = [
        proofs2[0],
        proofs0[1],
        proofs1[2],
        proofs0[3],
        proofs2[4],
        proofs1[5],
    ]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_max_cell_indices(spec):
    blob = VALID_BLOBS[3]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    # Use the highest valid cell indices
    max_index = spec.CELLS_PER_EXT_BLOB - 1
    indices = [max_index, max_index - 1, max_index - 2]
    commitments = [commitment]
    commitment_indices = [0] * len(indices)
    cell_indices = indices
    cosets_evals = [spec.cell_to_coset_evals(cells[i]) for i in indices]
    proofs_selected = [proofs[i] for i in indices]

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_compute_verify_cell_kzg_proof_batch_challenge_case_all_cells(spec):
    blob = VALID_BLOBS[4]
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    commitment = spec.blob_to_kzg_commitment(blob)

    # Use all cells
    num_cells = spec.CELLS_PER_EXT_BLOB
    commitments = [commitment]
    commitment_indices = [0] * num_cells
    cell_indices = list(range(num_cells))
    cosets_evals = [spec.cell_to_coset_evals(cells[i]) for i in range(num_cells)]
    proofs_selected = proofs

    yield from _run_compute_verify_cell_kzg_proof_batch_challenge_test(
        spec,
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs_selected,
    )
