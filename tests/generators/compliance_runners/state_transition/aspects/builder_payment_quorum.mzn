% Reusable payment-weight / quorum comparison relation.
include "base.mzn";

predicate builder_payment_quorum_ok(var Dim: relation, var bool: applicable) =
    (relation == NA <-> not applicable) /\
    (applicable -> relation in CMP);

function var bool: meets_builder_payment_quorum(var Dim: relation) = relation in {EQ, GT};
