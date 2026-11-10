import json
from pathlib import Path

import pytest

from . import xmss

KAT = json.loads((Path(__file__).parent / "xmss_kat.json").read_text())
PUBKEY = bytes.fromhex(KAT["pubkey"])
MESSAGE = bytes.fromhex(KAT["message"])
SIGNATURE = bytes.fromhex(KAT["signature"])
LEAF_INDEX = KAT["leaf_index"]
OTHER_PUBKEY = xmss.StubPk(1)


@pytest.fixture(autouse=True)
def active_xmss():
    old_state = xmss.xmss_active
    xmss.xmss_active = True
    yield
    xmss.xmss_active = old_state


def test_verify():
    assert xmss.Verify(PUBKEY, LEAF_INDEX, MESSAGE, SIGNATURE)


def test_verify_wrong_leaf_index():
    assert not xmss.Verify(PUBKEY, LEAF_INDEX + 1, MESSAGE, SIGNATURE)


def test_verify_wrong_message():
    assert not xmss.Verify(PUBKEY, LEAF_INDEX, b"\x00" * 32, SIGNATURE)


def test_verify_wrong_pubkey():
    assert not xmss.Verify(OTHER_PUBKEY, LEAF_INDEX, MESSAGE, SIGNATURE)


def test_verify_malformed_signature():
    assert not xmss.Verify(PUBKEY, LEAF_INDEX, MESSAGE, SIGNATURE[:-1])


def test_inactive_stubs():
    xmss.xmss_active = False
    assert xmss.Sign(1, LEAF_INDEX, MESSAGE) == xmss.STUB_SIGNATURE
    assert xmss.Verify(OTHER_PUBKEY, LEAF_INDEX, MESSAGE, SIGNATURE)
    assert xmss.SkToPk(1) == xmss.StubPk(1)
