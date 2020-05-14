// SPDX-License-Identifier: Apache-2.0

pragma solidity ^0.6.0;

// This interface is designed to be compatible with the Vyper version.
interface IDepositContract {
    event DepositEvent(
        bytes pubkey,
        bytes withdrawal_credentials,
        bytes amount,
        bytes signature,
        bytes index
    );

    function deposit(
        bytes calldata pubkey,
        bytes calldata withdrawal_credentials,
        bytes calldata signature,
        bytes32 deposit_data_root
    ) external payable;

    function get_deposit_root() external view returns (bytes32);

    function get_deposit_count() external view returns (bytes memory);
}

// Based on official specification in https://eips.ethereum.org/EIPS/eip-165
interface ERC165 {
    /// @notice Query if a contract implements an interface
    /// @param interfaceId The interface identifier, as specified in ERC-165
    /// @dev Interface identification is specified in ERC-165. This function
    ///  uses less than 30,000 gas.
    /// @return `true` if the contract implements `interfaceId` and
    ///  `interfaceId` is not 0xffffffff, `false` otherwise
    function supportsInterface(bytes4 interfaceId) external pure returns (bool);
}

// This is a rewrite of the Vyper Eth2.0 deposit contract in Solidity.
// It tries to stay as close as possible to the original source code.
contract DepositContract is IDepositContract, ERC165 {
    uint constant GWEI = 1e9;

    uint constant MIN_DEPOSIT_AMOUNT = 1 ether;
    uint constant DEPOSIT_CONTRACT_TREE_DEPTH = 32;
    // NOTE: this also ensures `deposit_count` will fit into 64-bits
    uint constant MAX_DEPOSIT_COUNT = 2**DEPOSIT_CONTRACT_TREE_DEPTH - 1;
    uint constant PUBKEY_LENGTH = 48; // bytes
    uint constant WITHDRAWAL_CREDENTIALS_LENGTH = 32; // bytes
    uint constant SIGNATURE_LENGTH = 96; // bytes

    bytes32[DEPOSIT_CONTRACT_TREE_DEPTH] branch;
    uint256 deposit_count;

    bytes32[DEPOSIT_CONTRACT_TREE_DEPTH] zero_hashes;

    constructor() public {
        // Compute hashes in empty sparse Merkle tree
        for (uint height = 0; height < DEPOSIT_CONTRACT_TREE_DEPTH - 1; height++)
            zero_hashes[height + 1] = sha256(abi.encodePacked(zero_hashes[height], zero_hashes[height]));
    }

    function get_deposit_root() override external view returns (bytes32) {
        bytes32 node;
        uint size = deposit_count;
        for (uint height = 0; height < DEPOSIT_CONTRACT_TREE_DEPTH; height++) {
            if ((size & 1) == 1)
                node = sha256(abi.encodePacked(branch[height], node));
            else
                node = sha256(abi.encodePacked(node, zero_hashes[height]));
            size /= 2;
        }
        return sha256(abi.encodePacked(
            node,
            to_little_endian_64(uint64(deposit_count)),
            bytes24(0)
        ));
    }

    function get_deposit_count() override external view returns (bytes memory) {
        return to_little_endian_64(uint64(deposit_count));
    }

    function deposit(
        bytes calldata pubkey,
        bytes calldata withdrawal_credentials,
        bytes calldata signature,
        bytes32 deposit_data_root
    ) override external payable {
        // Extended ABI length checks since dynamic types are used.
        require(pubkey.length == PUBKEY_LENGTH, "DepositContract: invalid pubkey length");
        require(withdrawal_credentials.length == WITHDRAWAL_CREDENTIALS_LENGTH, "DepositContract: invalid withdrawal_credentials length");
        require(signature.length == SIGNATURE_LENGTH, "DepositContract: invalid signature length");

        // Avoid overflowing the Merkle tree (and prevent edge case in computing `branch`)
        require(deposit_count < MAX_DEPOSIT_COUNT, "DepositContract: merkle tree full");

        // Check deposit amount
        require(msg.value >= MIN_DEPOSIT_AMOUNT, "DepositContract: deposit value too low");
        require(msg.value % GWEI == 0, "DepositContract: deposit value not multiple of gwei");
        uint deposit_amount = msg.value / GWEI;
        require(deposit_amount < 2**64, "DepositContract: deposit value too high");

        // Emit `DepositEvent` log
        bytes memory amount = to_little_endian_64(uint64(deposit_amount));
        emit DepositEvent(
            pubkey,
            withdrawal_credentials,
            amount,
            signature,
            to_little_endian_64(uint64(deposit_count))
        );

        // Compute deposit data root (`DepositData` hash tree root)
        bytes32 pubkey_root = sha256(abi.encodePacked(pubkey, bytes16(0)));
        bytes32 signature_root = sha256(abi.encodePacked(
            sha256(abi.encodePacked(bytes(signature[:64]))),
            sha256(abi.encodePacked(bytes(signature[64:]), bytes32(0)))
        ));
        bytes32 node = sha256(abi.encodePacked(
            sha256(abi.encodePacked(pubkey_root, withdrawal_credentials)),
            sha256(abi.encodePacked(amount, bytes24(0), signature_root))
        ));
        // Verify computed and expected deposit data roots match
        require(node == deposit_data_root, "DepositContract: reconstructed DepositData does not match supplied deposit_data_root");

        // Add deposit data root to Merkle tree (update a single `branch` node)
        deposit_count += 1;
        uint size = deposit_count;
        for (uint height = 0; height < DEPOSIT_CONTRACT_TREE_DEPTH; height++) {
            if ((size & 1) == 1) {
                branch[height] = node;
                return;
            }
            node = sha256(abi.encodePacked(branch[height], node));
            size /= 2;
        }
        // As the loop should always end prematurely with the `return` statement,
        // this code should be unreachable. We assert `false` just to be safe.
        assert(false);
    }

    function supportsInterface(bytes4 interfaceId) override external pure returns (bool) {
        return interfaceId == type(ERC165).interfaceId || interfaceId == type(IDepositContract).interfaceId;
    }

    function to_little_endian_64(uint64 value) internal pure returns (bytes memory ret) {
        // Unrolled the loop here.
        ret = new bytes(8);
        ret[0] = bytes1(uint8(value));
        ret[1] = bytes1(uint8(value >> 8));
        ret[2] = bytes1(uint8(value >> 16));
        ret[3] = bytes1(uint8(value >> 24));
        ret[4] = bytes1(uint8(value >> 32));
        ret[5] = bytes1(uint8(value >> 40));
        ret[6] = bytes1(uint8(value >> 48));
        ret[7] = bytes1(uint8(value >> 56));
    }
}
