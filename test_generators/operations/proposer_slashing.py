from eth_utils import (
    to_dict,
    to_tuple,
)

from eth2spec.phase0.spec import (
    BeaconBlockHeader,
    BeaconState,
    ProposerSlashing,
    apply_constants_preset,
    get_epoch_start_slot,
    process_proposer_slashing,
    MIN_DEPOSIT_AMOUNT,
    MAX_EFFECTIVE_BALANCE,
)
from eth2spec.debug.encode import encode

from gen_base import (
    gen_suite,
    gen_typing,
)

from preset_loader import loader

import keys
import genesis


NUM_VALIDATORS = 100


@to_dict
def valid():
    yield 'description', 'valid proposer slashing'

    deposits = genesis.create_deposits(
        keys.pubkeys[:NUM_VALIDATORS],
        keys.withdrawal_creds[:NUM_VALIDATORS],
    )
    state = genesis.create_genesis_state(deposits)
    yield 'pre', encode(state, BeaconState)

    header_1 = BeaconBlockHeader(state_root=b"\x00" * 32)
    header_2 = BeaconBlockHeader(state_root=b"\x11" * 32)
    proposer_slashing = ProposerSlashing(
        proposer_index=3,
        header_1=header_1,
        header_2=header_2,
    )
    yield 'proposer_slashing', encode(proposer_slashing, ProposerSlashing)

    process_proposer_slashing(state, proposer_slashing)
    yield 'post', encode(state, BeaconState)


@to_dict
def invalid_wrong_index():
    yield 'description', 'slashing validator with index out of bounds'

    deposits = genesis.create_deposits(
        keys.pubkeys[:NUM_VALIDATORS],
        keys.withdrawal_creds[:NUM_VALIDATORS],
    )
    state = genesis.create_genesis_state(deposits)
    yield 'pre', encode(state, BeaconState)

    header_1 = BeaconBlockHeader(state_root=b"\x00" * 32)
    header_2 = BeaconBlockHeader(state_root=b"\x11" * 32)
    proposer_slashing = ProposerSlashing(
        proposer_index=NUM_VALIDATORS,
        header_1=header_1,
        header_2=header_2,
    )
    yield 'proposer_slashing', encode(proposer_slashing, ProposerSlashing)

    try:
        process_proposer_slashing(state, proposer_slashing)
    except IndexError:
        pass
    else:
        assert False
    yield 'post', None


@to_dict
def invalid_different_epoch():
    yield 'description', 'slashing validator for headers from two different epochs'
    deposits = genesis.create_deposits(
        keys.pubkeys[:NUM_VALIDATORS],
        keys.withdrawal_creds[:NUM_VALIDATORS],
    )
    state = genesis.create_genesis_state(deposits)
    yield 'pre', encode(state, BeaconState)

    header_1 = BeaconBlockHeader(
        state_root=b"\x00" * 32,
        slot=get_epoch_start_slot(0),
    )
    header_2 = BeaconBlockHeader(
        state_root=b"\x11" * 32,
        slot=get_epoch_start_slot(1),
    )
    proposer_slashing = ProposerSlashing(
        proposer_index=3,
        header_1=header_1,
        header_2=header_2,
    )
    yield 'proposer_slashing', encode(proposer_slashing, ProposerSlashing)

    try:
        process_proposer_slashing(state, proposer_slashing)
    except AssertionError:
        pass
    else:
        assert False
    yield 'post', None


@to_dict
def invalid_same_headers():
    yield 'description', 'slashing validator with only one header'

    deposits = genesis.create_deposits(
        keys.pubkeys[:NUM_VALIDATORS],
        keys.withdrawal_creds[:NUM_VALIDATORS],
    )
    state = genesis.create_genesis_state(deposits)
    yield 'pre', encode(state, BeaconState)

    header_1 = BeaconBlockHeader(
        state_root=b"\x00" * 32,
    )
    proposer_slashing = ProposerSlashing(
        proposer_index=3,
        header_1=header_1,
        header_2=header_1,
    )
    yield 'proposer_slashing', encode(proposer_slashing, ProposerSlashing)

    try:
        process_proposer_slashing(state, proposer_slashing)
    except AssertionError:
        pass
    else:
        assert False
    yield 'post', None


@to_dict
def invalid_not_active():
    yield 'description', 'slashing validator who is not active yet'

    deposits = genesis.create_deposits(
        keys.pubkeys[:NUM_VALIDATORS],
        keys.withdrawal_creds[:NUM_VALIDATORS],
        amounts=[MIN_DEPOSIT_AMOUNT] + [MAX_EFFECTIVE_BALANCE] * (NUM_VALIDATORS - 1)
    )
    state = genesis.create_genesis_state(deposits)
    yield 'pre', encode(state, BeaconState)

    header_1 = BeaconBlockHeader(
        state_root=b"\x00" * 32,
    )
    header_2 = BeaconBlockHeader(
        state_root=b"\x11" * 32,
    )
    proposer_slashing = ProposerSlashing(
        proposer_index=0,
        header_1=header_1,
        header_2=header_2,
    )
    yield 'proposer_slashing', encode(proposer_slashing, ProposerSlashing)

    try:
        process_proposer_slashing(state, proposer_slashing)
    except AssertionError:
        pass
    else:
        assert False
    yield 'post', None


@to_tuple
def proposer_slashing_cases():
    yield valid()
    yield invalid_wrong_index()
    yield invalid_different_epoch()
    yield invalid_same_headers()
    yield invalid_not_active()


def mini_proposer_slashing_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    apply_constants_preset(presets)

    return ("proposer_slashing_minimal", "proposer_slashing", gen_suite.render_suite(
        title="proposer slashing operation",
        summary="Test suite for proposer slashing operation processing",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        runner="operations",
        handler="proposer_slashing",
        test_cases=proposer_slashing_cases()))


def full_proposer_slashing_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    apply_constants_preset(presets)

    return ("proposer_slashing_full", "proposer_slashing", gen_suite.render_suite(
        title="proposer slashing operation",
        summary="Test suite for proposer slashing operation processing",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="operations",
        handler="proposer_slashing",
        test_cases=proposer_slashing_cases()))
