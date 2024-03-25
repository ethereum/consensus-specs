from random import Random
from eth2spec.utils import bls
from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.keys import privkeys


def prepare_signed_consolidations(spec, state, index_pairs, fork_version=None):
    def create_signed_consolidation(source_index, target_index):
        consolidation = spec.Consolidation(
            epoch=spec.get_current_epoch(state),
            source_index=source_index,
            target_index=target_index,
        )
        return sign_consolidation(spec, state, consolidation, privkeys[source_index], privkeys[target_index], fork_version=fork_version)

    return [create_signed_consolidation(source_index, target_index) for (source_index, target_index) in index_pairs]

def sign_consolidation(spec, state, consolidation, source_privkey, target_privkey, fork_version=None):
    domain = spec.compute_domain(spec.DOMAIN_CONSOLIDATION, genesis_validators_root=state.genesis_validators_root)
    signing_root = spec.compute_signing_root(consolidation, domain)
    return spec.SignedConsolidation(
        message=consolidation,
        signature=bls.Aggregate([bls.Sign(source_privkey, signing_root), bls.Sign(target_privkey, signing_root)])
    )

def run_consolidation_processing(spec, state, signed_consolidation, valid=True):
    """
    Run ``process_consolidation``, yielding:
      - pre-state ('pre')
      - consolidation ('consolidation')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    source_validator = state.validators[signed_consolidation.message.source_index]
    target_validator = state.validators[signed_consolidation.message.target_index]

    yield 'pre', state
    yield 'consolidation', signed_consolidation

    if not valid:
        expect_assertion_error(lambda: spec.process_consolidation(state, signed_consolidation))
        yield 'post', None
        return


    pre_exit_epoch = source_validator.exit_epoch

    spec.process_consolidation(state, signed_consolidation)

    yield 'post', state

    assert source_validator.withdrawal_credentials[1:] == target_validator.withdrawal_credentials[1:]
    assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.validators[signed_consolidation.message.source_index].exit_epoch < spec.FAR_FUTURE_EPOCH
    assert state.validators[signed_consolidation.message.source_index].exit_epoch == state.earliest_consolidation_epoch
    assert state.pending_consolidations[len(state.pending_consolidations)-1] == spec.PendingConsolidation(
        source_index = signed_consolidation.message.source_index,
        target_index = signed_consolidation.message.target_index
        )

