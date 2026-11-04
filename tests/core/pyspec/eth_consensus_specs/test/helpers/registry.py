from eth_consensus_specs.test.helpers.forks import is_post_pq
from eth_consensus_specs.test.helpers.keys import xmss_builder_pubkeys, xmss_pubkeys


def get_validators(spec, state):
    """
    The validator registry that the state transition reads and writes, which
    moves to ``state.pq_validators`` from PQ onwards.
    """
    return state.pq_validators if is_post_pq(spec) else state.validators


def get_builders(spec, state):
    """
    The builder registry that the state transition reads and writes, which
    moves to ``state.pq_builders`` from PQ onwards.
    """
    return state.pq_builders if is_post_pq(spec) else state.builders


def to_pq_validator(spec, validator, index):
    """
    The PQ record of ``validator``, with the placeholder XMSS public key of the
    validator at ``index``.
    """
    return spec.PQValidator(
        pubkey=xmss_pubkeys[index],
        withdrawal_credentials=validator.withdrawal_credentials,
        effective_balance=validator.effective_balance,
        slashed=validator.slashed,
        activation_eligibility_epoch=validator.activation_eligibility_epoch,
        activation_epoch=validator.activation_epoch,
        exit_epoch=validator.exit_epoch,
        withdrawable_epoch=validator.withdrawable_epoch,
    )


def to_pq_builder(spec, builder, index):
    """
    The PQ record of ``builder``, with the placeholder XMSS public key of the
    builder at ``index``.
    """
    return spec.PQBuilder(
        pubkey=xmss_builder_pubkeys[index],
        version=builder.version,
        execution_address=builder.execution_address,
        balance=builder.balance,
        deposit_epoch=builder.deposit_epoch,
        withdrawable_epoch=builder.withdrawable_epoch,
    )


def append_validator(spec, state, validator):
    """
    Append ``validator`` to the registry, and from PQ onwards also its PQ record.
    """
    index = len(state.validators)
    state.validators.append(validator)
    if is_post_pq(spec):
        state.pq_validators.append(to_pq_validator(spec, validator, index))


def append_builder(spec, state, builder):
    """
    Append ``builder`` to the registry, and from PQ onwards also its PQ record.
    """
    index = len(state.builders)
    state.builders.append(builder)
    if is_post_pq(spec):
        state.pq_builders.append(to_pq_builder(spec, builder, index))


def set_validators(spec, state, validators):
    """
    Replace the registry with ``validators``, and from PQ onwards their PQ records.
    """
    state.validators = spec.Validators(data=validators)
    if is_post_pq(spec):
        state.pq_validators = spec.PQValidators(
            data=[to_pq_validator(spec, validator, i) for i, validator in enumerate(validators)]
        )


def set_builders(spec, state, builders):
    """
    Replace the registry with ``builders``, and from PQ onwards their PQ records.
    """
    state.builders = spec.Builders(data=builders)
    if is_post_pq(spec):
        state.pq_builders = spec.PQBuilders(
            data=[to_pq_builder(spec, builder, i) for i, builder in enumerate(builders)]
        )
