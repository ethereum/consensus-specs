from eth2spec.utils.ssz.ssz_impl import serialize, hash_tree_root
from eth2spec.utils.ssz.ssz_typing import (
    Bit, Bytes, uint64, Container, Vector, List
)

from eth2spec.utils.ssz.ssz_partials import (
    ssz_full, ssz_partial, extract_value_at_path, merge
)


class Person(Container):
    is_male: Bit
    age: uint64
    name: Bytes[32]


class City(Container):
    coords: Vector[uint64, 2]
    people: List[Person, 20]


people = List[Person, 20](
    Person(is_male=True, age=uint64(45), name=Bytes[32](b"Alex")),
    Person(is_male=True, age=uint64(47), name=Bytes[32](b"Bob")),
    Person(is_male=True, age=uint64(49), name=Bytes[32](b"Carl")),
    Person(is_male=True, age=uint64(51), name=Bytes[32](b"Danny")),
    Person(is_male=True, age=uint64(53), name=Bytes[32](b"Evan")),
    Person(is_male=False, age=uint64(55), name=Bytes[32](b"Fae")),
    Person(is_male=False, age=uint64(57), name=Bytes[32](b"Ginny")),
    Person(is_male=False, age=uint64(59), name=Bytes[32](b"Heather")),
    Person(is_male=False, age=uint64(61), name=Bytes[32](b"Ingrid")),
    Person(is_male=False, age=uint64(63), name=Bytes[32](b"Kane")),
)

city = City(coords=Vector[uint64, 2](uint64(45), uint64(90)), people=people)

paths = [
    ["coords", 0],
    ["people", 4, "name", 1],
    ["people", 8, "is_male"],
    ["people", 9],
    ["people", 7],
    ["people", 1],
]

x = ssz_full(city)
full = ssz_partial(City, ssz_full(city))
print(full.objects.keys())
for path in paths:
    print(path, list(full.access_partial(path).objects.keys()))
    # print(path, get_nodes_along_path(full, path, typ=City).keys())
p = merge(*[full.access_partial(path) for path in paths])
# p = SSZPartial(infer_type(city), branch2)
assert p.coords[0] == city.coords[0] == extract_value_at_path(p.objects, City, ['coords', 0])
assert p.coords[1] == city.coords[1]
assert len(p.coords) == len(city.coords)
assert p.coords.hash_tree_root() == hash_tree_root(city.coords)
assert p.people[4].name[1] == city.people[4].name[1] == extract_value_at_path(p.objects, City, ['people', 4, 'name', 1])
assert len(p.people[4].name) == len(city.people[4].name) == 4
assert p.people[8].is_male == city.people[8].is_male
assert p.people[7].is_male == city.people[7].is_male
assert p.people[7].age == city.people[7].age
assert p.people[7].name[0] == city.people[7].name[0]
assert str(p.people[7].name) == str(city.people[7].name)
assert str(p.people[1]) == str(city.people[1]), (str(p.people[1]), str(city.people[1]))
assert p.people[1].name.hash_tree_root() == hash_tree_root(city.people[1].name)
assert p.people[1].hash_tree_root() == hash_tree_root(city.people[1])
assert p.coords.hash_tree_root() == hash_tree_root(city.coords)
assert p.people.hash_tree_root() == hash_tree_root(city.people), (
    p.people.hash_tree_root(), hash_tree_root(city.people))
assert p.hash_tree_root() == hash_tree_root(city)
print(hash_tree_root(city))
print("Reading tests passed")
p.coords[0] = 65
assert p.coords[0] == 65
assert p.coords.hash_tree_root() == hash_tree_root(Vector[uint64, 2](uint64(65), uint64(90)))
p.people[7].name[0] = byte('F')
assert p.people[7].name[0] == ord('F')
assert p.people[7].name == Bytes[32](b"Feather")
p.people[9].is_male = False
assert p.people[9].is_male is False
p.people[1].name = Bytes[32](b"Ashley")
assert p.people[1].name.full_value() == Bytes[32](b"Ashley")
p.people[1].age += 100
assert p.people[1].hash_tree_root() == hash_tree_root(Person(is_male=True, age=uint64(147), name=Bytes[32](b"Ashley")))
print("Writing tests passed")
p = merge(*[full.access_partial(path) for path in paths])
object_keys = sorted(list(p.objects.keys()))[::-1]
print(object_keys)
pre_hash_root = p.hash_tree_root()
for i in range(10):
    p.people.append(Person(is_male=False, age=uint64(i), name=Bytes[32](b"z" * i)))
    city.people.append(Person(is_male=False, age=uint64(i), name=Bytes[32](b"z" * i)))
    p.people[7].name.append(byte('!'))
    city.people[7].name.append(byte('!'))
    assert p.hash_tree_root() == city.hash_tree_root()
    print(i)
for i in range(10):
    p.people.pop()
    city.people.pop()
    p.people[7].name.pop()
    city.people[7].name.pop()
    assert p.hash_tree_root() == city.hash_tree_root()
    print(i)
assert p.hash_tree_root() == pre_hash_root
print("Append and pop tests passed")
encoded = p.encode()
print(encoded)
print(serialize(encoded))
assert encoded.to_ssz(City).hash_tree_root() == p.hash_tree_root()
# print('extras', list([k for k in p.objects if k not in encoded.to_ssz(City).objects]))
print("Encoded partial tests passed")
