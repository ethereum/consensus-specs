from utils.ssz.ssz_typing import *
from utils.ssz.ssz_impl import *
from utils.ssz.ssz_partials import *
import os, random

class Person(Container):
    is_male: bool
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
    ["people", 9, "is_male"],
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
object_keys = sorted(list(p.objects.keys()))[::-1]
# p = SSZPartial(infer_type(city), branch2)
assert p.coords[0] == city.coords[0]
assert p.coords[1] == city.coords[1]
assert len(p.coords) == len(city.coords)
assert p.coords.hash_tree_root() == hash_tree_root(city.coords)
assert p.people[4].name[1] == city.people[4].name[1]
assert len(p.people[4].name) == len(city.people[4].name)
assert p.people[9].is_male == city.people[9].is_male
assert p.people[7].is_male == city.people[7].is_male
assert p.people[7].age == city.people[7].age
assert p.people[7].name[0] == city.people[7].name[0]
assert str(p.people[7].name) == city.people[7].name.items.decode('utf-8')
assert str(p.people[1]) == str(city.people[1]), (str(p.people[1]), str(city.people[1]))
assert p.people[1].name.hash_tree_root() == hash_tree_root(city.people[1].name)
assert p.people[1].hash_tree_root() == hash_tree_root(city.people[1])
assert p.coords.hash_tree_root() == hash_tree_root(city.coords)
assert p.people.hash_tree_root() == hash_tree_root(city.people), (p.people.hash_tree_root(), hash_tree_root(city.people))
assert p.hash_tree_root() == hash_tree_root(city)
print(hash_tree_root(city))
print("Tests passed")
