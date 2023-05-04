import rlp
from rlp.sedes import (
    BigEndianInt,
    Binary,
    CountableList,
    big_endian_int,
    binary,
)

address = Binary.fixed_length(20, allow_empty=True)
hash32 = Binary.fixed_length(32)
int32 = BigEndianInt(32)


class AccountAccesses(rlp.Serializable):
    fields = [
        ('account', address),
        ('storage_keys', CountableList(hash32)),
    ]


class SignedBlobTransaction(rlp.Serializable):
    fields = [
        ('chain_id', big_endian_int),
        ('nonce', big_endian_int),
        ('max_priority_fee_per_gas', big_endian_int),
        ('gas_limit', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
        ('access_list', CountableList(AccountAccesses)),
        ('max_fee_per_gas', big_endian_int),
        ('blob_versioned_hashes', CountableList(hash32)),
        ('y_parity', big_endian_int),  # v
        ('r', big_endian_int),
        ('s', big_endian_int),
    ]


def get_sample_signed_blob_tx(blob_versioned_hashes):
    return SignedBlobTransaction(
        chain_id=0,
        nonce=1,
        max_priority_fee_per_gas=2,
        gas_limit=55667788,
        to=b'\x11' * 20,
        value=123,
        data=b'',
        access_list=(AccountAccesses(account=b'\x22' * 20, storage_keys=[b'\x33' * 32]),),
        max_fee_per_gas=1,
        blob_versioned_hashes=blob_versioned_hashes,
        y_parity=2,
        r=3,
        s=4,
    )
