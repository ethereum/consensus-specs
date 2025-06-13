include "globals.mzn";

int: numOfEpochs = 4;
int: maxEpoch = numOfEpochs - 1;
set of int: EPOCH = 0..maxEpoch;

type BS = record(EPOCH: e, EPOCH: je, EPOCH: uje);


var BS: block;
var EPOCH: curr_e;
var EPOCH: store_je;

function var EPOCH: get_vse(var BS: block) =
  if block.e < curr_e then block.uje else block.je endif;

predicate valid_block_epochs(var BS: block) =
  block.e <= curr_e /\
  block.je <= block.uje /\ (block.e != 0 -> block.je < block.e) /\ block.uje <= block.e;

predicate valid_store_je() =
  let { var BS: best_block; constraint valid_block_epochs(best_block); }
  in get_vse(best_block) = store_je;


constraint valid_store_je();
constraint get_vse(block) <= store_je;
constraint valid_block_epochs(block);


bool: store_je_eq_zero = false;
bool: block_vse_eq_store_je = false;
bool: prev_e_justified = false;
bool: block_uje_ge_store_je = false;
bool: block_vse_plus_two_ge_curr_e = false;
%bool: block_is_leaf;
%bool: block_descendant_of_store_just_root;
%bool: block_descendant_of_store_fin_chkpt;
%bool: block_fe_eq_zero = false;

constraint store_je_eq_zero <-> store_je == 0;
constraint block_vse_eq_store_je <-> get_vse(block) == store_je;
constraint prev_e_justified <-> store_je == curr_e - 1;
constraint block_uje_ge_store_je <-> block.uje >= store_je;
constraint block_vse_plus_two_ge_curr_e <-> get_vse(block) + 2 >= curr_e;
