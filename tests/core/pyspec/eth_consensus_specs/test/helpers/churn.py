"""
Fork-aware churn helpers.

Gloas (EIP-8061) splits the single Electra-era ``get_activation_exit_churn_limit``
into separate ``get_activation_churn_limit`` and ``get_exit_churn_limit``
functions, each driven by its own quotient. Tests that need to know the
per-epoch activation, exit, or validator-count churn should call these helpers
so they pick the right spec function for the active fork.
"""

from eth_consensus_specs.test.helpers.forks import is_post_gloas


def get_activation_churn_limit(spec, state):
    """Per-epoch activation/deposit churn (gloas: ``get_activation_churn_limit``)."""
    if is_post_gloas(spec):
        return spec.get_activation_churn_limit(state)
    return spec.get_activation_exit_churn_limit(state)


def get_exit_churn_limit(spec, state):
    """Per-epoch exit churn (gloas: ``get_exit_churn_limit``)."""
    if is_post_gloas(spec):
        return spec.get_exit_churn_limit(state)
    return spec.get_activation_exit_churn_limit(state)


def get_validator_exit_count_per_epoch(spec, state):
    """How many ``MIN_ACTIVATION_BALANCE`` validators can exit per epoch — count-based
    pre-gloas, derived from the balance-based exit churn limit on gloas+."""
    if is_post_gloas(spec):
        return get_exit_churn_limit(spec, state) // spec.MIN_ACTIVATION_BALANCE
    return spec.get_validator_churn_limit(state)
