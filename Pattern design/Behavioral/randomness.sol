// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleRandom {
    // Simple random number generator
    function simpleRandomNumber() internal view returns (uint) {
    return uint(blockhash(block.number - 1));
    }
    // Generate random based on time, address and block difficulty
    function random() public view returns (uint) {
        return uint(keccak256(abi.encodePacked(block.timestamp, msg.sender, block.difficulty)));
    }
}

