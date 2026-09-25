% Realization aspect for the exit and consolidation churn queue helpers.
%
% RESET_FIT starts a new queue epoch, CARRY_FIT reuses an existing queue with
% enough remaining churn, and CARRY_OVERFLOW reuses a later queue epoch with
% insufficient remaining churn.  The latter is materialized with a small
% remainder so one request spans multiple additional epochs.

enum QueueChurnVariant = { QUEUE_CHURN_NA, RESET_FIT, CARRY_FIT, CARRY_OVERFLOW };
var QueueChurnVariant: churn_variant;
