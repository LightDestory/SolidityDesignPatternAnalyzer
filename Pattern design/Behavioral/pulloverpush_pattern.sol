// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Example of an auction contract with a pullover pattern
contract Auction {
  address public highestBidder;
  uint highestBid;
  mapping(address => uint) refunds;

  function bid() public payable {
    require(msg.value >= highestBid);
    if (highestBidder != address(0)) {
      // record the underlying bid to be refund
      refunds[highestBidder] += highestBid; 
    }
    highestBidder = msg.sender;
    highestBid = msg.value;
  }
  
  function withdrawRefund() public {
    uint refund = refunds[msg.sender];
    refunds[msg.sender] = 0;
    payable(msg.sender).transfer(refund);
  }
}
