from eth2spec.utils.minimal_ssz import hash_tree_root


def encode(value, typ, include_hash_tree_roots=False):
    if isinstance(typ, str) and typ[:4] == 'uint':
        if typ[4:] == '128' or typ[4:] == '256':
            return str(value)
        return value
    elif typ == 'bool':
        assert value in (True, False)
        return value
    elif isinstance(typ, list):
        return [encode(element, typ[0], include_hash_tree_roots) for element in value]
    elif isinstance(typ, str) and typ[:4] == 'byte':
        return '0x' + value.hex()
    elif hasattr(typ, 'fields'):
        ret = {}
        for field, subtype in typ.fields.items():
            ret[field] = encode(getattr(value, field), subtype, include_hash_tree_roots)
            if include_hash_tree_roots:
                ret[field + "_hash_tree_root"] = '0x' + hash_tree_root(getattr(value, field), subtype).hex()
        if include_hash_tree_roots:
            ret["hash_tree_root"] = '0x' + hash_tree_root(value, typ).hex()
        return ret
    else:
        print(value, typ)
        raise Exception("Type not recognized")
