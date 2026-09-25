% Relational coverage model: process_sync_aggregate (Gloas).
enum ParticipationLevel = { FULL, MAJORITY, EMPTY };
enum Outcome = { ACCEPT, REJECT_SIGNATURE };

var ParticipationLevel: participation_level;
var bool: signature_valid;
var Outcome: outcome;

constraint signature_valid <-> outcome == ACCEPT;
