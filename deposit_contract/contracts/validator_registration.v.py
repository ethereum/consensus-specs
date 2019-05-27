MIN_DEPOSIT_AMOUNT: constant(uint256) = 1000000000  # Gwei
FULL_DEPOSIT_AMOUNT: constant(uint256) = 32000000000  # Gwei
CHAIN_START_FULL_DEPOSIT_THRESHOLD: constant(uint256) = 65536  # 2**16
DEPOSIT_CONTRACT_TREE_DEPTH: constant(uint256) = 32
SECONDS_PER_DAY: constant(uint256) = 86400
MAX_64_BIT_VALUE: constant(uint256) = 18446744073709551615  # 2**64 - 1

Deposit: event({
    pubkey: bytes[48],
    withdrawal_credentials: bytes[32],
    amount: bytes[8],
    signature: bytes[96],
    merkle_tree_index: bytes[8],
})
Eth2Genesis: event({deposit_root: bytes32, deposit_count: bytes[8], time: bytes[8]})

zerohashes: bytes32[DEPOSIT_CONTRACT_TREE_DEPTH]
branch: bytes32[DEPOSIT_CONTRACT_TREE_DEPTH]
deposit_count: uint256
full_deposit_count: uint256
chainStarted: public(bool)


@public
def __init__():
    for i in range(DEPOSIT_CONTRACT_TREE_DEPTH - 1):
        self.zerohashes[i+1] = sha256(concat(self.zerohashes[i], self.zerohashes[i]))
        self.branch[i+1] = self.zerohashes[i + 1]


@public
@constant
def to_little_endian_64(value: uint256) -> bytes[8]:
    assert value <= MAX_64_BIT_VALUE

    # array access for bytes[] not currently supported in vyper so
    # reversing bytes using bitwise uint256 manipulations
    y: uint256 = 0
    x: uint256 = value
    for i in range(8):
        y = shift(y, 8)
        y = y + bitwise_and(x, 255)
        x = shift(x, -8)

    return slice(convert(y, bytes32), start=24, len=8)


@public
@constant
def from_little_endian_64(value: bytes[8]) -> uint256:
    y: uint256 = 0
    x: uint256 = convert(value, uint256)
    for i in range(8):
        y = y + shift(bitwise_and(x, 255), 8 * (7-i))
        x = shift(x, -8)

    return y


@public
@constant
def get_deposit_root() -> bytes32:
    root: bytes32 = 0x0000000000000000000000000000000000000000000000000000000000000000
    size: uint256 = self.deposit_count
    for h in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        if bitwise_and(size, 1) == 1:
            root = sha256(concat(self.branch[h], root))
        else:
            root = sha256(concat(root, self.zerohashes[h]))
        size /= 2
    return root

@public
@constant
def get_deposit_count() -> bytes[8]:
    return self.to_little_endian_64(self.deposit_count)

@payable
@public
def deposit(pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96]):
    deposit_amount: uint256 = msg.value / as_wei_value(1, "gwei")
    assert deposit_amount >= MIN_DEPOSIT_AMOUNT
    amount: bytes[8] = self.to_little_endian_64(deposit_amount)

    index: uint256 = self.deposit_count

    # add deposit to merkle tree
    i: int128 = 0
    power_of_two: uint256 = 2
    for _ in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        if (index+1) % power_of_two != 0:
            break
        i += 1
        power_of_two *= 2

    zero_bytes_32: bytes32
    pubkey_root: bytes32 = sha256(concat(pubkey, slice(zero_bytes_32, start=0, len=16)))
    signature_root: bytes32 = sha256(concat(
        sha256(slice(signature, start=0, len=64)),
        sha256(concat(slice(signature, start=64, len=32), zero_bytes_32))
    ))
    value: bytes32 = sha256(concat(
        sha256(concat(pubkey_root, withdrawal_credentials)),
        sha256(concat(
            amount,
            slice(zero_bytes_32, start=0, len=24),
            signature_root,
        ))
    ))
    for j in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        if j < i:
            value = sha256(concat(self.branch[j], value))
        else:
            break
    self.branch[i] = value

    self.deposit_count += 1
    new_deposit_root: bytes32 = self.get_deposit_root()
    log.Deposit(
        pubkey,
        withdrawal_credentials,
        amount,
        signature,
        self.to_little_endian_64(index),
    )

    if deposit_amount >= FULL_DEPOSIT_AMOUNT:
        self.full_deposit_count += 1
        if self.full_deposit_count == CHAIN_START_FULL_DEPOSIT_THRESHOLD:
            timestamp_day_boundary: uint256 = (
                as_unitless_number(block.timestamp) -
                as_unitless_number(block.timestamp) % SECONDS_PER_DAY +
                2 * SECONDS_PER_DAY
            )
            log.Eth2Genesis(new_deposit_root,
                            self.to_little_endian_64(self.deposit_count),
                            self.to_little_endian_64(timestamp_day_boundary))
            self.chainStarted = True
