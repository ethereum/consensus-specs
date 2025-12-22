from eth_utils import encode_hex


def output_fast_confirmation_checks(spec, store, test_steps):
    test_steps.append(
        {
            "checks": {
                "previous_epoch_observed_justified_checkpoint": {
                    "epoch": int(store.previous_epoch_observed_justified_checkpoint.epoch),
                    "root": encode_hex(store.previous_epoch_observed_justified_checkpoint.root),
                },
                "current_epoch_observed_justified_checkpoint": {
                    "epoch": int(store.current_epoch_observed_justified_checkpoint.epoch),
                    "root": encode_hex(store.current_epoch_observed_justified_checkpoint.root),
                },
                "previous_slot_head": encode_hex(store.previous_slot_head),
                "current_slot_head": encode_hex(store.current_slot_head),
                "confirmed_root": encode_hex(store.confirmed_root),
            }
        }
    )


def on_slot_start_after_past_attestations_applied_and_append_step(spec, store, test_steps):
    spec.on_slot_start_after_past_attestations_applied(store)
    test_steps.append(
        {"slot_start_after_past_attestations_applied": int(spec.get_current_slot(store))}
    )
    output_fast_confirmation_checks(spec, store, test_steps)
