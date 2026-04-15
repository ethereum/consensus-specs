# Fast confirmation tests

The aim of the fast confirmation tests is to provide test coverage for Fast
Confirmation Rule. This test format extennds the
[Fork choice](../fork_choice/README.md) test format by introducing additional
checks verifying the state of the fast confirmation store.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Test case format](#test-case-format)
  - [`steps.yaml`](#stepsyaml)
    - [`on_fast_confirmation` execution](#on_fast_confirmation-execution)
    - [Checks step](#checks-step)

<!-- mdformat-toc end -->

## Test case format

### `steps.yaml`

#### `on_fast_confirmation` execution

There is no explicit `on_fast_confirmation` execution step. The test generator
implicitly runs `on_fast_confirmation` at the start of each slot after all past
slot attestations are applied to the fork choice `store`. Each time this happens
Fast confirmation checks are yielded.

#### Checks step

Checks to verify the current status of `fcr_store: FastConfirmationStore`:

```yaml
previous_epoch_observed_justified_checkpoint: {
    epoch: int,               -- Integer value from fast_confirmation_store.previous_epoch_observed_justified_checkpoint.epoch
    root: string,             -- Encoded 32-byte value from fast_confirmation_store.previous_epoch_observed_justified_checkpoint.root
}
current_epoch_observed_justified_checkpoint: {
    epoch: int,               -- Integer value from fast_confirmation_store.current_epoch_observed_justified_checkpoint.epoch
    root: string,             -- Encoded 32-byte value from fast_confirmation_store.current_epoch_observed_justified_checkpoint.root
}
previous_epoch_greatest_unrealized_checkpoint: {
    epoch: int,               -- Integer value from fast_confirmation_store.previous_epoch_greatest_unrealized_checkpoint.epoch
    root: string,             -- Encoded 32-byte value from fast_confirmation_store.previous_epoch_greatest_unrealized_checkpoint.root
}
previous_slot_head: string    -- Encoded 32-byte value of fast_confirmation_store.previous_slot_head
current_slot_head: string     -- Encoded 32-byte value of fast_confirmation_store.current_slot_head
confirmed_root: string        -- Encoded 32-byte value of fast_confirmation_store.confirmed_root
```

For example:

```yaml
- checks:
    time: 60
    head:
      slot: 9
      root: '0x74fd665ecd799b1a1a17cb62ff635d9209c77defe98bf1f6c92f9f3306125315'
    justified_checkpoint:
      epoch: 0
      root: '0xeb7ad3d90729a187da87dcf467eace66b12331f9fcbd38c26e9d94c1c5cbc26f'
    finalized_checkpoint:
      epoch: 0
      root: '0xeb7ad3d90729a187da87dcf467eace66b12331f9fcbd38c26e9d94c1c5cbc26f'
    proposer_boost_root: '0x0000000000000000000000000000000000000000000000000000000000000000'
    previous_epoch_observed_justified_checkpoint:
      epoch: 0
      root: '0xeb7ad3d90729a187da87dcf467eace66b12331f9fcbd38c26e9d94c1c5cbc26f'
    current_epoch_observed_justified_checkpoint:
      epoch: 0
      root: '0xeb7ad3d90729a187da87dcf467eace66b12331f9fcbd38c26e9d94c1c5cbc26f'
    previous_epoch_greatest_unrealized_checkpoint:
      epoch: 0
      root: '0xeb7ad3d90729a187da87dcf467eace66b12331f9fcbd38c26e9d94c1c5cbc26f'
    previous_slot_head: '0xc648137aa42ba6bde20090fc1cfb6382f37a8e79f159ca5e8b64870763d13f54'
    current_slot_head: '0x74fd665ecd799b1a1a17cb62ff635d9209c77defe98bf1f6c92f9f3306125315'
    confirmed_root: '0x74fd665ecd799b1a1a17cb62ff635d9209c77defe98bf1f6c92f9f3306125315'
```
