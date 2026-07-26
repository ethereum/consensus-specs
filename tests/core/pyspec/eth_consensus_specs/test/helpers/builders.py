"""Helper functions for builder registry management in tests."""


def add_builder_to_registry(
    spec,
    state,
    builder_index,
    pubkey=None,
    execution_address=None,
    balance=None,
    deposit_epoch=None,
    withdrawable_epoch=None,
):
    """
    Add or update a builder in state.builders registry.

    Args:
        spec: The spec object
        state: The beacon state to modify
        builder_index: The index for the builder in the registry
        pubkey: Builder's BLS public key (default: derived from builder_index)
        execution_address: Builder's execution layer address (default: derived from builder_index)
        balance: Builder's balance in Gwei (default: spec.MIN_DEPOSIT_AMOUNT)
        deposit_epoch: Epoch when builder deposited (default: 0)
        withdrawable_epoch: Epoch when builder can withdraw (default: spec.FAR_FUTURE_EPOCH)
    """
    # Grow registry if needed
    while len(state.builders) <= builder_index:
        state.builders.append(spec.Builder())

    # Set builder properties
    builder = state.builders[builder_index]
    builder.pubkey = pubkey if pubkey is not None else builder_index.to_bytes(48, "little")
    builder.execution_address = (
        execution_address if execution_address is not None else builder_index.to_bytes(20, "little")
    )
    builder.balance = balance if balance is not None else spec.MIN_DEPOSIT_AMOUNT
    builder.deposit_epoch = deposit_epoch if deposit_epoch is not None else 0
    builder.withdrawable_epoch = (
        withdrawable_epoch if withdrawable_epoch is not None else spec.FAR_FUTURE_EPOCH
    )
    builder.version = 0


def set_builder_balance(spec, state, builder_index, balance):
    """
    Set builder balance, creating the builder if it doesn't exist.

    Args:
        spec: The spec object
        state: The beacon state to modify
        builder_index: The index for the builder in the registry
        balance: The balance to set in Gwei
    """
    if builder_index >= len(state.builders):
        add_builder_to_registry(spec, state, builder_index)
    state.builders[builder_index].balance = balance
