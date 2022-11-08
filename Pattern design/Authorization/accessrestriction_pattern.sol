// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AccessRestriction {
    // Current time
    uint256 public creationTime = block.timestamp;
    // Check time difference
    modifier onlyBefore(uint256 _time) {
        require(block.timestamp < _time);
        _;
    }
    // Check time difference
    modifier onlyAfter(uint256 _time) {
        require(block.timestamp > _time);
        _;
    }
    // Check msg sender
    modifier onlyBy(address account) {
        require(msg.sender == account);
        _;
    }
    // Check generic boolean condition
    modifier condition(bool _condition) {
        require(_condition);
        _;
    }
    // Check minimum transaction value
    modifier minAmount(uint256 _amount) {
        require(msg.value >= _amount);
        _;
    }

    function test()
        public
        payable
        onlyBefore(creationTime + 10 seconds)
        minAmount(1 ether)
    {
        // Do something
    }
}
