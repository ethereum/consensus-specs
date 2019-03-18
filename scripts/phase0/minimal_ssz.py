from utils.hash import hash


BYTES_PER_CHUNK = 32
BYTES_PER_LENGTH_PREFIX = 4
ZERO_CHUNK = b'\x00' * BYTES_PER_CHUNK

def SSZType(fields):
    class SSZObject():
        def __init__(self, **kwargs):
            for f in fields:
                if f not in kwargs:
                    raise Exception("Missing constructor argument: %s" % f)
                setattr(self, f, kwargs[f])

        def __eq__(self, other):
            return (
                self.fields == other.fields and
                self.serialize() == other.serialize()
            )

        def __hash__(self):
            return int.from_bytes(self.hash_tree_root(), byteorder="little")

        def __str__(self):
            output = []
            for field in self.fields:
                output.append(f'{field}: {getattr(self, field)}')
            return "\n".join(output)

        def serialize(self):
            return serialize_value(self, self.__class__)

        def hash_tree_root(self):
            return hash_tree_root(self, self.__class__)

    SSZObject.fields = fields
    return SSZObject

class Vector(list):
    def __init__(self, x):
        list.__init__(self, x)
        self.length = len(x)

    def append(*args):
        raise Exception("Cannot change the length of a vector")

    remove = clear = extend = pop = insert = append

def is_basic(typ):
    return isinstance(typ, str) and (typ[:4] in ('uint', 'bool') or typ == 'byte')

def is_constant_sized(typ):
    if is_basic(typ):
        return True
    elif isinstance(typ, list) and len(typ) == 1:
        return is_constant_sized(typ[0])
    elif isinstance(typ, list) and len(typ) == 2:
        return False
    elif isinstance(typ, str) and typ[:5] == 'bytes':
        return len(typ) > 5
    elif hasattr(typ, 'fields'):
        for subtype in typ.fields.values():
            if not is_constant_sized(subtype):
                return False
        return True
    else:
        raise Exception("Type not recognized")

def coerce_to_bytes(x):
    if isinstance(x, str):
        o = x.encode('utf-8')
        assert len(o) == len(x)
        return o
    elif isinstance(x, bytes):
        return x
    else:
        raise Exception("Expecting bytes")

def serialize_value(value, typ=None):
    if typ is None:
        typ = infer_type(value)
    if isinstance(typ, str) and typ[:4] == 'uint':
        length = int(typ[4:])
        assert length in (8, 16, 32, 64, 128, 256)
        return value.to_bytes(length // 8, 'little')
    elif typ == 'bool':
        assert value in (True, False)
        return b'\x01' if value is True else b'\x00'
    elif (isinstance(typ, list) and len(typ) == 1) or typ == 'bytes':
        serialized_bytes = coerce_to_bytes(value) if typ == 'bytes' else b''.join([serialize_value(element, typ[0]) for element in value])
        assert len(serialized_bytes) < 2**(8 * BYTES_PER_LENGTH_PREFIX)
        serialized_length = len(serialized_bytes).to_bytes(BYTES_PER_LENGTH_PREFIX, 'little')
        return serialized_length + serialized_bytes
    elif isinstance(typ, list) and len(typ) == 2:
        assert len(value) == typ[1]
        return b''.join([serialize_value(element, typ[0]) for element in value])
    elif isinstance(typ, str) and len(typ) > 5 and typ[:5] == 'bytes':
        assert len(value) == int(typ[5:]), (value, int(typ[5:]))
        return coerce_to_bytes(value)
    elif hasattr(typ, 'fields'):
        serialized_bytes = b''.join([serialize_value(getattr(value, field), subtype) for field, subtype in typ.fields.items()])
        if is_constant_sized(typ):
            return serialized_bytes
        else:
            assert len(serialized_bytes) < 2**(8 * BYTES_PER_LENGTH_PREFIX)
            serialized_length = len(serialized_bytes).to_bytes(BYTES_PER_LENGTH_PREFIX, 'little')
            return serialized_length + serialized_bytes
    else:
        print(value, typ)
        raise Exception("Type not recognized")

def chunkify(bytez):
    bytez += b'\x00' * (-len(bytez) % BYTES_PER_CHUNK)
    return [bytez[i:i+32] for i in range(0, len(bytez), 32)]

def pack(values, subtype):
    return chunkify(b''.join([serialize_value(value, subtype) for value in values]))

def is_power_of_two(x):
    return x > 0 and x & (x-1) == 0

def merkleize(chunks):
    tree = chunks[::]
    while not is_power_of_two(len(tree)):
        tree.append(ZERO_CHUNK)
    tree = [ZERO_CHUNK] * len(tree) + tree
    for i in range(len(tree)//2-1, 0, -1):
        tree[i] = hash(tree[i*2] + tree[i*2+1])
    return tree[1]

def mix_in_length(root, length):
    return hash(root + length.to_bytes(32, 'little'))

def infer_type(value):
    if hasattr(value.__class__, 'fields'):
        return value.__class__
    elif isinstance(value, Vector):
        return [infer_type(value[0]) if len(value) > 0 else 'uint64', len(value)]
    elif isinstance(value, list):
        return [infer_type(value[0])] if len(value) > 0 else ['uint64']
    elif isinstance(value, (bytes, str)):
        return 'bytes'
    elif isinstance(value, int):
        return 'uint64'
    else:
        raise Exception("Failed to infer type")

def hash_tree_root(value, typ=None):
    if typ is None:
        typ = infer_type(value)
    if is_basic(typ):
        return merkleize(pack([value], typ))
    elif isinstance(typ, list) and len(typ) == 1 and is_basic(typ[0]):
        return mix_in_length(merkleize(pack(value, typ[0])), len(value))
    elif isinstance(typ, list) and len(typ) == 1 and not is_basic(typ[0]):
        return mix_in_length(merkleize([hash_tree_root(element, typ[0]) for element in value]), len(value))
    elif isinstance(typ, list) and len(typ) == 2 and is_basic(typ[0]):
        assert len(value) == typ[1]
        return merkleize(pack(value, typ[0]))
    elif typ == 'bytes':
        return mix_in_length(merkleize(chunkify(coerce_to_bytes(value))), len(value))
    elif isinstance(typ, str) and typ[:5] == 'bytes' and len(typ) > 5:
        assert len(value) == int(typ[5:])
        return merkleize(chunkify(coerce_to_bytes(value)))
    elif isinstance(typ, list) and len(typ) == 2 and not is_basic(typ[0]):
        return merkleize([hash_tree_root(element, typ[0]) for element in value])
    elif hasattr(typ, 'fields'):
        return merkleize([hash_tree_root(getattr(value, field), subtype) for field, subtype in typ.fields.items()])
    else:
        raise Exception("Type not recognized")

def truncate(container):
    field_keys = list(container.fields.keys())
    truncated_fields = {
        key: container.fields[key]
        for key in field_keys[:-1]
    }
    truncated_class = SSZType(truncated_fields)
    kwargs = {
        field: getattr(container, field)
        for field in field_keys[:-1]
    }
    return truncated_class(**kwargs)

def signed_root(container):
    return hash_tree_root(truncate(container))

def serialize(ssz_object):
    return getattr(ssz_object, 'serialize')()
