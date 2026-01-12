"""Unit tests for builder helper functions."""

from unittest.mock import MagicMock

from tests.infra.helpers.builders import (
    add_builder_to_registry,
    set_builder_balance,
)


class TestAddBuilderToRegistry:
    """Test suite for add_builder_to_registry function."""

    def test_add_builder_to_empty_registry(self):
        """Test adding a builder when registry is empty."""
        spec = MagicMock()
        spec.Builder = MagicMock
        spec.MIN_DEPOSIT_AMOUNT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1

        state = MagicMock()
        state.builders = []

        add_builder_to_registry(spec, state, builder_index=0)

        assert len(state.builders) == 1
        builder = state.builders[0]
        assert builder.pubkey == (0).to_bytes(48, "little")
        assert builder.execution_address == (0).to_bytes(20, "little")
        assert builder.balance == spec.MIN_DEPOSIT_AMOUNT
        assert builder.deposit_epoch == 0
        assert builder.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
        assert builder.version == 0

    def test_add_builder_grows_registry(self):
        """Test that registry grows to accommodate builder_index."""
        spec = MagicMock()
        spec.Builder = MagicMock
        spec.MIN_DEPOSIT_AMOUNT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1

        state = MagicMock()
        state.builders = []

        add_builder_to_registry(spec, state, builder_index=5)

        # Should have 6 builders (indices 0-5)
        assert len(state.builders) == 6

    def test_add_builder_with_custom_values(self):
        """Test adding a builder with custom pubkey, address, and balance."""
        spec = MagicMock()
        spec.Builder = MagicMock
        spec.MIN_DEPOSIT_AMOUNT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1

        state = MagicMock()
        state.builders = []

        custom_pubkey = b"\xab" * 48
        custom_address = b"\xcd" * 20
        custom_balance = 5_000_000_000
        custom_deposit_epoch = 100
        custom_withdrawable_epoch = 200

        add_builder_to_registry(
            spec,
            state,
            builder_index=0,
            pubkey=custom_pubkey,
            execution_address=custom_address,
            balance=custom_balance,
            deposit_epoch=custom_deposit_epoch,
            withdrawable_epoch=custom_withdrawable_epoch,
        )

        builder = state.builders[0]
        assert builder.pubkey == custom_pubkey
        assert builder.execution_address == custom_address
        assert builder.balance == custom_balance
        assert builder.deposit_epoch == custom_deposit_epoch
        assert builder.withdrawable_epoch == custom_withdrawable_epoch

    def test_add_builder_updates_existing(self):
        """Test that adding to existing index updates the builder."""
        spec = MagicMock()
        spec.Builder = MagicMock
        spec.MIN_DEPOSIT_AMOUNT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1

        existing_builder = MagicMock()
        state = MagicMock()
        state.builders = [existing_builder]

        new_balance = 9_000_000_000
        add_builder_to_registry(spec, state, builder_index=0, balance=new_balance)

        # Should update existing builder, not create new one
        assert len(state.builders) == 1
        assert state.builders[0].balance == new_balance


class TestSetBuilderBalance:
    """Test suite for set_builder_balance function."""

    def test_set_balance_existing_builder(self):
        """Test setting balance on an existing builder."""
        spec = MagicMock()

        existing_builder = MagicMock()
        existing_builder.balance = 1_000_000_000
        state = MagicMock()
        state.builders = [existing_builder]

        new_balance = 5_000_000_000
        set_builder_balance(spec, state, builder_index=0, balance=new_balance)

        assert state.builders[0].balance == new_balance

    def test_set_balance_creates_builder(self):
        """Test that set_builder_balance creates builder if it doesn't exist."""
        spec = MagicMock()
        spec.Builder = MagicMock
        spec.MIN_DEPOSIT_AMOUNT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1

        state = MagicMock()
        state.builders = []

        new_balance = 3_000_000_000
        set_builder_balance(spec, state, builder_index=0, balance=new_balance)

        assert len(state.builders) == 1
        assert state.builders[0].balance == new_balance
