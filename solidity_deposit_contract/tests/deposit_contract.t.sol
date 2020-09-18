pragma solidity ^0.6.2;

import "../lib/ds-test/src/test.sol";

import "./vyper_setup.sol";
import "../deposit_contract.sol";

contract DepositContractTest is DSTest {
  DepositContract depositContract_sol;
  DepositContract depositContract_vyp;
  uint64 constant GWEI = 1000000000;

  function setUp() public {
    VyperSetup vyperSetup = new VyperSetup();
    depositContract_vyp = DepositContract(vyperSetup.deployDeposit());
    depositContract_sol = new DepositContract();
  }

  // --- SUCCESS TESTS ---

  // Tests initialized storage values, comparing vyper and solidity
  function test_empty_root() public {
    bytes32 zHash = 0x0000000000000000000000000000000000000000000000000000000000000000;
    bytes32 zHashN = zHash;
    for (uint i = 0; i <= 31; i++) {
      zHashN = sha256(abi.encodePacked(zHashN, zHashN));
    }
    assertEq(sha256(abi.encodePacked(zHashN, zHash)), depositContract_vyp.get_deposit_root());
    assertEq(depositContract_sol.get_deposit_root(),  depositContract_vyp.get_deposit_root());
  }

  // Generates 16 random deposits, insert them in both vyper and solidity version and compare get_deposit_root after each insertion
  function test_16_deposits(bytes32[16] memory pubkey_one, bytes16[16] memory pubkey_two, bytes32[16] memory _withdrawal_credentials,
                            bytes32[16] memory sig_one, bytes32[16] memory sig_two, bytes32[16] memory sig_three, uint32[16] memory amount) public {
    uint j;
    for (uint i = 0; i < 16; i++) {
      // as of dcaa774, the solidity version is more restrictive than vyper and requires deposits to be divisible by GWEI
      uint64 gweiamount = amount[i] * GWEI;
      if (1 ether <= gweiamount) {
        j++;
        deposit_in(depositContract_sol, pubkey_one[i], pubkey_two[i], _withdrawal_credentials[i], sig_one[i], sig_two[i], sig_three[i], gweiamount);
        deposit_in(depositContract_vyp, pubkey_one[i], pubkey_two[i], _withdrawal_credentials[i], sig_one[i], sig_two[i], sig_three[i], gweiamount);

        assertEq(depositContract_sol.get_deposit_root(), depositContract_vyp.get_deposit_root());
        assertEq(keccak256(abi.encodePacked(depositContract_sol.get_deposit_count())), keccak256(abi.encodePacked(depositContract_vyp.get_deposit_count())));
        assertEq(keccak256(abi.encodePacked(depositContract_sol.get_deposit_count())), keccak256(to_little_endian_64(uint64(j))));
      }
    }
  }

  // The solidity contract fails when given a deposit which is not divisible by GWEI

  function testFail_deposit_not_divisible_by_gwei(bytes32 pubkey_one, bytes16 pubkey_two, bytes32 _withdrawal_credentials,
                                                  bytes32 sig_one, bytes32 sig_two, bytes32 sig_three) public {
    deposit_in(depositContract_sol, pubkey_one, pubkey_two, _withdrawal_credentials, sig_one, sig_two, sig_three, 1 ether + 1);
  }

  // --- FAILURE TESTS ---

  // if the node is given randomly instead of as the ssz root, the chances of success are so unlikely that we can assert it to be false
  function testFail_malformed_node_vyp(bytes32 pubkey_one, bytes16 pubkey_two, bytes32 _withdrawal_credentials, bytes32 sig_one,
                                       bytes32 sig_two, bytes32 sig_three, uint64 amount, bytes32 node) public {
    bytes memory pubkey = abi.encodePacked(pubkey_one, pubkey_two);
    bytes memory withdrawal_credentials = abi.encodePacked(_withdrawal_credentials); //I wish just recasting to `bytes` would work..
    bytes memory signature = abi.encodePacked(sig_one, sig_two, sig_three);
    depositContract_vyp.deposit{value: amount}(pubkey, withdrawal_credentials, signature, node);
  }

  // If the node is taken randomly instead of as the ssz root, the chances of success are so unlikely that we can assert it to be false
  function testFail_malformed_node_sol(bytes32 pubkey_one, bytes16 pubkey_two, bytes32 _withdrawal_credentials, bytes32 sig_one,
                                       bytes32 sig_two, bytes32 sig_three, uint64 amount, bytes32 node) public {
    bytes memory pubkey = abi.encodePacked(pubkey_one, pubkey_two);
    bytes memory withdrawal_credentials = abi.encodePacked(_withdrawal_credentials);
    bytes memory signature = abi.encodePacked(sig_one, sig_two, sig_three);
    depositContract_sol.deposit{value: amount}(pubkey, withdrawal_credentials, signature, node);
  }

  // if bytes lengths are wrong, the call will fail
  function testFail_malformed_calldata_vyp(bytes memory pubkey, bytes memory withdrawal_credentials, bytes memory signature, uint64 amount) public {
    if (amount >= 1000000000000000000) {
      if (!(pubkey.length == 48 && withdrawal_credentials.length == 32 && signature.length == 96)) {
        depositContract_vyp.deposit{value: amount}(pubkey, withdrawal_credentials, signature,
                                                  encode_node(pubkey, withdrawal_credentials, signature, to_little_endian_64(amount / GWEI))
                                                 );
      } else { revert(); }
    } else { revert(); }
  }

  function testFail_malformed_calldata_sol(bytes memory pubkey, bytes memory withdrawal_credentials, bytes memory signature, uint64 amount) public {
    if (amount >= 1000000000000000000) {
      if (!(pubkey.length == 48 && withdrawal_credentials.length == 32 && signature.length == 96)) {
        depositContract_sol.deposit{value: amount}(pubkey, withdrawal_credentials, signature,
                                                  encode_node(pubkey, withdrawal_credentials, signature, to_little_endian_64(amount / GWEI))
                                                 );
      } else { revert(); }
    } else { revert(); }
  }

  // --- HELPER FUNCTIONS ---

  function deposit_in(DepositContract depositContract, bytes32 pubkey_one, bytes16 pubkey_two, bytes32 _withdrawal_credentials, bytes32 sig_one, bytes32 sig_two, bytes32 sig_three, uint64 amount) public {
    bytes memory pubkey = abi.encodePacked(pubkey_one, pubkey_two);
    bytes memory withdrawal_credentials = abi.encodePacked(_withdrawal_credentials);
    bytes memory signature = abi.encodePacked(sig_one, sig_two, sig_three);
    bytes32 node = encode_node(pubkey, withdrawal_credentials, signature, to_little_endian_64(amount / GWEI));
    depositContract.deposit{value: amount}(pubkey, withdrawal_credentials, signature, node);
  }

  function slice(bytes memory a, uint32 offset, uint32 size) pure internal returns (bytes memory result) {
    result = new bytes(size);
    for (uint i = 0; i < size; i++) {
      result[i] = a[offset + i];
    }
  }

  function encode_node(bytes memory pubkey, bytes memory withdrawal_credentials, bytes memory signature, bytes memory amount) public pure returns (bytes32) {
    bytes16 zero_bytes16;
    bytes24 zero_bytes24;
    bytes32 zero_bytes32;
    bytes32 pubkey_root = sha256(abi.encodePacked(pubkey, zero_bytes16));
    bytes32 signature_root = sha256(abi.encodePacked(
      sha256(abi.encodePacked(slice(signature, 0, 64))),
      sha256(abi.encodePacked(slice(signature, 64, 32), zero_bytes32))
    ));
    return sha256(abi.encodePacked(
      sha256(abi.encodePacked(pubkey_root, withdrawal_credentials)),
      sha256(abi.encodePacked(amount, zero_bytes24, signature_root))
    ));
  }

  function to_little_endian_64(uint64 value) internal pure returns (bytes memory ret) {
    ret = new bytes(8);
    ret[0] = bytes1(uint8(value & 0xff));
    ret[1] = bytes1(uint8((value >> 8) & 0xff));
    ret[2] = bytes1(uint8((value >> 16) & 0xff));
    ret[3] = bytes1(uint8((value >> 24) & 0xff));
    ret[4] = bytes1(uint8((value >> 32) & 0xff));
    ret[5] = bytes1(uint8((value >> 40) & 0xff));
    ret[6] = bytes1(uint8((value >> 48) & 0xff));
    ret[7] = bytes1(uint8((value >> 56) & 0xff));
  }
}
