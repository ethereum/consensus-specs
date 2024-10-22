include "globals.mzn";

int: AE; % anchor epoch
int: NE; % num of epochs
int: NL; % num of super-majority links

set of int: EPOCH = AE..(AE+NE-1);
set of int: LINKS = 0..(NL-1);

array[LINKS] of var EPOCH: sources;
array[LINKS] of var EPOCH: targets;

predicate surround_vote(var LINKS: a, var LINKS: b) =
  sources[a] < sources[b] /\ targets[b] < targets[a];

constraint forall(i in LINKS)(sources[i] < targets[i]);
constraint forall(i in LINKS)(sources[i] == AE \/ member(targets, sources[i]));
constraint strictly_increasing(targets);
constraint forall(i,j in LINKS where i != j)(not surround_vote(i,j));

% Exclude (1, 2) SM link which is unreachable for the Gasper protocol
constraint forall(i in LINKS)(not (sources[i] == 1 /\ targets[i] == 2));
