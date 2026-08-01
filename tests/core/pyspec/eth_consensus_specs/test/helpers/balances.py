from eth_consensus_specs.test.helpers.forks import is_post_electra


def get_min_activation_balance(spec):
    """
    Returns the minimum activation balance. Electra introduced
    ``MIN_ACTIVATION_BALANCE``; before Electra the equivalent value was
    ``MAX_EFFECTIVE_BALANCE``.
    """
    if is_post_electra(spec):
        return spec.MIN_ACTIVATION_BALANCE
    return spec.MAX_EFFECTIVE_BALANCE
