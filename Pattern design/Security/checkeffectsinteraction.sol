// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Example of a bank account with balance withdrawal
contract ChecksEffectsInteractions {
    mapping(address => uint256) balances;

    function deposit() public payable {
        balances[msg.sender] = msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        // Update the state before sending Ether to prevent reentrancy
        balances[msg.sender] -= amount;
        // Perform the transfer
        payable(msg.sender).transfer(amount);
    }
}
