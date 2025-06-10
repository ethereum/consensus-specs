include "globals.mzn";

int: numOfEpochs = 5;
int: maxEpoch = numOfEpochs-1;
set of int: EPOCH = 0..maxEpoch;
int: numOfLinks = 3;
set of int: LINKS = 0..numOfLinks-1;


array[EPOCH] of var EPOCH: epochs;
array[EPOCH] of var EPOCH: pjes;
array[EPOCH] of var EPOCH: cjes;

array[LINKS] of var EPOCH: sources;
array[LINKS] of var EPOCH: targets;


predicate ex_link(var EPOCH: src, var EPOCH: tgt) =
  exists(i in LINKS)(sources[i] == src /\ targets[i] == tgt);


predicate trans(EPOCH: from, EPOCH: to) =
  let {
    var EPOCH: e = epochs[from]; var EPOCH: cje = cjes[from]; var EPOCH: pje = pjes[from];
    var EPOCH: ne = epochs[to]; var EPOCH: ncje = cjes[to]; var EPOCH: npje = pjes[to];
    var bool: curr_link = ex_link(cje, e); var bool: prev_link = (e > 0) -> ex_link(pje, e-1);
  } in
    ((curr_link /\ ncje == e)
      \/ (prev_link /\ ncje == e-1)
      \/ (ncje == cje))
    /\ npje == cje /\ ne == e + 1
;


predicate surround_vote(var LINKS: a, var LINKS: b) =
  sources[a] < sources[b] /\ targets[b] < targets[a];


constraint forall(i in LINKS)(sources[i] < targets[i]);
constraint forall(i in LINKS)(sources[i] == 0 \/ member(targets, sources[i]));
constraint strictly_increasing(targets);
constraint forall(i,j in LINKS where i != j)(not surround_vote(i,j));

constraint epochs[0] == 0;
constraint pjes[0] == 0;
constraint cjes[0] == 0;
constraint forall(i in 0..maxEpoch-1)(trans(i, i+1));


