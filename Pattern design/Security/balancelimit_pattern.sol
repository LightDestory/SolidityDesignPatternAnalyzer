// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract BalanceLimit {
    uint256 limit;

    constructor(uint256 _value) {
        limit = _value;
    }
    // Modifier to check if the balance is less than the limit
    modifier limitedPayable() {
        require(address(this).balance <= limit);
        _;
    }

    function deposit() public payable limitedPayable {
        // Some stuff
    }
}
