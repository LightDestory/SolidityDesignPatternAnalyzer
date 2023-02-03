// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Example of an deposit contract with a state machine pattern
contract DepositLock {
    enum Stages {
        AcceptingDeposits,
        FreezingDeposits,
        ReleasingDeposits
    }
    Stages public stage = Stages.AcceptingDeposits;
    uint256 public creationTime = block.timestamp;
    mapping(address => uint256) balances;

    modifier atStage(Stages _stage) {
        require(stage == _stage);
        _;
    }
    modifier timedTransitions() {
        if (stage == Stages.AcceptingDeposits && block.timestamp >= creationTime + 1 days) nextStage();
        if (stage == Stages.FreezingDeposits && block.timestamp >= creationTime + 8 days) nextStage();
        _;
    }
    function nextStage() internal {
        stage = Stages(uint256(stage) + 1);
    }
    function deposit() public payable timedTransitions atStage(Stages.AcceptingDeposits) {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public timedTransitions atStage(Stages.ReleasingDeposits) {
        uint256 amount = balances[msg.sender];
        balances[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }
}

