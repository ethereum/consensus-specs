def get_validators(spec, state):
    """
    The validator registry.
    """
    return state.validators


def get_builders(spec, state):
    """
    The builder registry.
    """
    return state.builders


def get_balances(spec, state):
    """
    The validator balances.
    """
    return state.balances


def set_balances(spec, state, balances):
    """
    Replace the validator balances with ``balances``.
    """
    state.balances = spec.Balances(data=balances)


def append_validator(spec, state, validator, balance):
    """
    Append ``validator`` with ``balance`` to the registry.
    """
    state.validators.append(validator)
    state.balances.append(balance)


def append_builder(spec, state, builder):
    """
    Append ``builder`` to the registry.
    """
    state.builders.append(builder)


def set_validators(spec, state, validators):
    """
    Replace the registry with ``validators``.
    """
    state.validators = spec.Validators(data=validators)


def set_builders(spec, state, builders):
    """
    Replace the registry with ``builders``.
    """
    state.builders = spec.Builders(data=builders)
