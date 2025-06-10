include "globals.mzn";

int: NE = 4;
int: NS = NE * 2;
int: NB = 5;

type Block = record(var SLOT: slot, var BLOCK: parent, var EPOCH: bje, var EPOCH: buje);

function var int: s2e(var int: e) = e div 2;
predicate valid_block(var BLOCK: b) =
  let {var int: ep = s2e(slot[b]); var int: je = bje[b]; var int: uje = buje[b]}
  in je <= uje /\ je <= ep /\ (ep != 0 -> je < ep) /\ uje <= ep;

set of int: BLOCK = 0..(NB-1);
set of int: SLOT = 0..(NS-1);
set of int: EPOCH = 0..(NE-1);
array[BLOCK] of var BLOCK: parent;
array[BLOCK] of var SLOT: slot;
array[BLOCK] of var EPOCH: bje;
array[BLOCK] of var EPOCH: buje;

var int: sje;
var int: suje;



constraint maximum(sje, bje);
constraint maximum(suje, buje);

constraint parent[0] == 0 /\ slot[0] == 0 /\ bje[0] == 0 /\ buje[0] == 0;
constraint forall(i in BLOCK)(if i == 0 then parent[i] == i else parent[i] != i endif);
constraint strictly_increasing(slot);
constraint forall(i in BLOCK)(valid_block(i));
constraint buje[NB-1] > 2;

constraint pred1 <-> is_leaf(block);
constraint pred2 <-> is_anscestor_of_sje(block);

solve satisfy;
