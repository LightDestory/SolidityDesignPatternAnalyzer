// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Guard check pattern
contract GuardCheck {
    function donate(address addr) payable public {
        require(addr != address(0));
        require(msg.value != 0);
        uint balanceBeforeTransfer = address(this).balance;
        uint transferAmount;
        if (addr.balance == 0) {
            transferAmount = msg.value;
        } else if (addr.balance < msg.sender.balance) {
            transferAmount = msg.value / 2;
        } else {
            // revert if the condition is not met
            revert();
        }
        payable(addr).transfer(transferAmount);
        // Check that the transfer was successful
        assert(address(this).balance == balanceBeforeTransfer - transferAmount);      
    }
}

