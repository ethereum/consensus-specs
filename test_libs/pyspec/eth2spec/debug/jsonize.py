from eth2spec.utils.minimal_ssz import hash_tree_root


def jsonize(value, typ, include_hash_tree_roots=False):
    if isinstance(typ, str) and typ[:4] == 'uint':
        return value
    elif typ == 'bool':
        assert value in (True, False)
        return value
    elif isinstance(typ, list):
        return [jsonize(element, typ[0], include_hash_tree_roots) for element in value]
    elif isinstance(typ, str) and typ[:4] == 'byte':
        return '0x' + value.hex()
    elif hasattr(typ, 'fields'):
        ret = {}
        for field, subtype in typ.fields.items():
            ret[field] = jsonize(getattr(value, field), subtype, include_hash_tree_roots)
            if include_hash_tree_roots:
                ret[field + "_hash_tree_root"] = '0x' + hash_tree_root(getattr(value, field), subtype).hex()
        if include_hash_tree_roots:
            ret["hash_tree_root"] = '0x' + hash_tree_root(value, typ).hex()
        return ret
    else:
        print(value, typ)
        raise Exception("Type not recognized")


def dejsonize(json, typ):
    if isinstance(typ, str) and typ[:4] == 'uint':
        return json
    elif typ == 'bool':
        assert json in (True, False)
        return json
    elif isinstance(typ, list):
        return [dejsonize(element, typ[0]) for element in json]
    elif isinstance(typ, str) and typ[:4] == 'byte':
        return bytes.fromhex(json[2:])
    elif hasattr(typ, 'fields'):
        temp = {}
        for field, subtype in typ.fields.items():
            temp[field] = dejsonize(json[field], subtype)
            if field + "_hash_tree_root" in json:
                assert(json[field + "_hash_tree_root"][2:] == 
                       hash_tree_root(temp[field], subtype).hex())
        ret = typ(**temp)
        if "hash_tree_root" in json:
            assert(json["hash_tree_root"][2:] == 
                   hash_tree_root(ret, typ).hex())
        return ret
    else:
        print(json, typ)
        raise Exception("Type not recognized")
