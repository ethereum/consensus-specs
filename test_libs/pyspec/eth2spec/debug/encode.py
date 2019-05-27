from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import *


def encode(value, typ, include_hash_tree_roots=False):
    if is_uint_type(typ):
        # Larger uints are boxed and the class declares their byte length
        if issubclass(typ, uint) and typ.byte_len > 8:
            return str(value)
        return value
    elif is_bool_type(typ):
        assert value in (True, False)
        return value
    elif is_list_type(typ) or is_vector_type(typ):
        elem_typ = read_elem_type(typ)
        return [encode(element, elem_typ, include_hash_tree_roots) for element in value]
    elif issubclass(typ, bytes): # both bytes and BytesN
        return '0x' + value.hex()
    elif is_container_type(typ):
        ret = {}
        for field, subtype in typ.get_fields():
            field_value = getattr(value, field)
            ret[field] = encode(field_value, subtype, include_hash_tree_roots)
            if include_hash_tree_roots:
                ret[field + "_hash_tree_root"] = '0x' + hash_tree_root(field_value, subtype).hex()
        if include_hash_tree_roots:
            ret["hash_tree_root"] = '0x' + hash_tree_root(value, typ).hex()
        return ret
    else:
        print(value, typ)
        raise Exception("Type not recognized")
