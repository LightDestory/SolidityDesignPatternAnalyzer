// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SpeedBumps {
    // Struct to store the data
    struct RequestedWithdrawal {
        uint256 amount;
        uint256 time;
    }
    // Mapping to track user's requested withdrawals
    mapping(address => uint256) private balances;
    mapping(address => RequestedWithdrawal) private requestedWithdrawals;
    uint256 constant withdrawalWaitPeriod = 28 days; // 4 weeks

    function requestWithdrawal() public {
        if (balances[msg.sender] > 0) {
            uint256 amountToWithdraw = balances[msg.sender];
            // For simplicity we take everything and suppose that no deposit are allowed meanwhile
            balances[msg.sender] = 0;
            requestedWithdrawals[msg.sender] = RequestedWithdrawal({
                amount: amountToWithdraw,
                time: block.timestamp
            });
        }
    }

    function withdraw() public {
        if (requestedWithdrawals[msg.sender].amount > 0 &&
            block.timestamp > requestedWithdrawals[msg.sender].time + withdrawalWaitPeriod) {
            uint256 amountToWithdraw = requestedWithdrawals[msg.sender].amount;
            requestedWithdrawals[msg.sender].amount = 0;
            require(payable(msg.sender).send(amountToWithdraw));
        }
    }
}
