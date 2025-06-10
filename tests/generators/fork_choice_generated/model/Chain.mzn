include "globals.mzn";

int: numOfEpochs = 5;
int: maxEpoch = numOfEpochs - 1;
set of int: EPOCH = 0..maxEpoch;

type SML = record(EPOCH: source, EPOCH: target);
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


type BSt = record(EPOCH: e, EPOCH: pje, EPOCH: cje);

predicate ok(var opt int: v) =
  not absent(v);

predicate ok_sml(var opt SML: sml) =
  ok(sml.source) /\ ok(sml.target);

predicate correct_sml(var opt SML: sml) =
  ok(sml.source) <-> ok(sml.target);

predicate valid_link(var opt SML: sml, var EPOCH: src, var EPOCH: tgt) =
    if ok_sml(sml) then
      sml.source == src /\ sml.target == tgt
    endif
  ;

function var BSt: epoch_trans(var BSt: block, var opt SML: p_sml, var opt SML: c_sml) =
  let {
    var EPOCH: new_pje = block.cje;
    var EPOCH: new_cje =
      if ok_sml(c_sml) /\ valid_link(c_sml, block.cje, block.e) then
        block.e
      else
        if ok_sml(p_sml) /\ valid_link(p_sml, block.pje, block.e-1) then
          block.e - 1
        else
          block.cje
        endif
      endif;
  } in (e: block.e + 1, pje: new_pje, cje: new_cje);


constraint valid_store_je();
constraint get_vse(block) <= store_je;
constraint valid_block_epochs(block);
%constraint block.e >= 2 /\ block.je >= 1;
%constraint block.je < block.uje /\ block.e < curr_e;


opt bool: store_je_eq_zero = true;
opt bool: block_vse_eq_store_je = <>;
opt bool: prev_e_justified = <>;
opt bool: block_uje_ge_store_je = <>;
opt bool: block_vse_plus_two_ge_curr_e = <>;
%bool: block_is_leaf;
%bool: block_descendant_of_store_just_root;
%bool: block_descendant_of_store_fin_chkpt;
%bool: block_fe_eq_zero = false;

constraint store_je_eq_zero <-> (store_je == 0);
constraint block_vse_eq_store_je <-> (get_vse(block) == store_je);
constraint prev_e_justified <-> (store_je == curr_e - 1);
constraint block_uje_ge_store_je <-> (block.uje >= store_je);
constraint block_vse_plus_two_ge_curr_e <-> (get_vse(block) + 2 >= curr_e);


predicate epoch_trans_p(var BSt: b, var opt SML: sml, var BSt: r) =
  r.e == b.e + 1
  /\ r.pje = b.cje
  /\ if ok_sml(sml) then
       (r.cje = b.e /\ sml.source = b.cje /\ sml.target = b.e)
       \/ (r.cje = b.e - 1 /\ sml.source = b.pje /\ sml.target = b.e-1)
     else
       r.cje = b.cje
     endif;

function var bool: etclo(array[0..maxE] of var BSt: sts, int: sz) =
  sts[0] = (e: 0, pje: 0, cje: 0)
  /\ forall(i in 0..sz-1) (epoch_trans_p(sts[i], smls[i], sts[i+1]));

array[0..maxE] of var BSt: sts;
array[0..maxE-1] of var opt SML: smls;
constraint etclo(sts, 2);
