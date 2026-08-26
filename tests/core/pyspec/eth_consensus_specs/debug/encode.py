from ssz.bitfields import BitList, BitVector, ProgressiveBitList
from ssz.boolean import Boolean
from ssz.byte_arrays import ByteList
from ssz.collections import List, ProgressiveList, Vector
from ssz.container import Container, ProgressiveContainer
from ssz.uint import BaseUint as Uint, Byte
from ssz.union import CompatibleUnion

from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root, serialize


def encode(value, include_hash_tree_roots=False):
    if isinstance(value, Uint):
        # Larger uints are boxed and the class declares their byte length
        if value.__class__.get_byte_length() > 8:
            return str(int(value))
        return int(value)
    elif isinstance(value, Boolean):
        return bool(value)
    elif isinstance(value, BitList | ProgressiveBitList | BitVector) or (
        isinstance(value, ProgressiveList) and issubclass(type(value).ELEMENT_TYPE, Byte)
    ):
        return "0x" + serialize(value).hex()
    elif isinstance(value, (list, List | ProgressiveList | Vector)):  # normal python lists
        return [encode(element, include_hash_tree_roots) for element in value]
    elif isinstance(value, bytes | ByteList):  # bytes, ByteList, ByteVector
        return "0x" + value.hex()
    elif isinstance(value, Container | ProgressiveContainer):
        ret = {}
        for field_name in type(value).model_fields:
            field_value = getattr(value, field_name)
            ret[field_name] = encode(field_value, include_hash_tree_roots)
            if include_hash_tree_roots:
                ret[field_name + "_hash_tree_root"] = "0x" + hash_tree_root(field_value).hex()
        if include_hash_tree_roots:
            ret["hash_tree_root"] = "0x" + hash_tree_root(value).hex()
        return ret
    elif isinstance(value, CompatibleUnion):
        return {
            "selector": encode(value.selector),
            "data": encode(value.data, include_hash_tree_roots),
        }
    else:
        raise Exception(f"Type not recognized: value={value}, typ={type(value)}")
