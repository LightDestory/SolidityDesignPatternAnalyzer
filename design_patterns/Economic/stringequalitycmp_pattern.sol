// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleContractExample {
    function hashCompareCheck(string memory _a, string memory _b) internal pure returns (bool) {
        return
            keccak256(abi.encodePacked(_a)) == keccak256(abi.encodePacked(_b));
    }

    // In cases of different length, the function will use less gas than the one above
    function hashCompareWithLengthCheck(string memory _a, string memory _b) internal pure returns (bool) {
        if (bytes(_a).length != bytes(_b).length) {
            return false;
        } else {
            return keccak256(abi.encodePacked(_a)) == keccak256(abi.encodePacked(_b));
        }
    }
}
