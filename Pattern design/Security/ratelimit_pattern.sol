// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RateLimiter {
    uint256 executions;
    uint256 enableEvery;
    uint256 nextReset;

    // Initialize reset time
    constructor(uint256 _resetInterval) {
        executions = 0;
        enableEvery = _resetInterval;
        nextReset = block.timestamp + _resetInterval;
    }
    // Reset execution count
    function reset() private {
        executions = 0;
        nextReset = block.timestamp + enableEvery;
    }
    // Modifier to limit execution
    modifier rateLimited(uint256 maxExecutions) {
        if (executions++ < maxExecutions) _;
        if (block.timestamp >= nextReset) reset();
    }
}
