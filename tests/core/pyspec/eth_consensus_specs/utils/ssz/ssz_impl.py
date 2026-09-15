from ssz.ssz_base import SSZType


def ssz_serialize(obj: SSZType) -> bytes:
    return obj.encode_bytes()


def serialize(obj: SSZType) -> bytes:
    return ssz_serialize(obj)


def ssz_deserialize[V: SSZType](typ: type[V], data: bytes) -> V:
    return typ.decode_bytes(data)


def deserialize[V: SSZType](typ: type[V], data: bytes) -> V:
    return ssz_deserialize(typ, data)
