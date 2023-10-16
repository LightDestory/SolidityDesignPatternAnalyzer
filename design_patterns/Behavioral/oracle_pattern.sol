// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Oracle pattern
contract Oracle {
    address knownSource = address(0x1234); // known source
    struct Request {
        bytes data;
        function(bytes memory) external callback;
    }
    Request[] requests;
    event NewRequest(uint256);
    modifier onlyBy(address account) {
        require(msg.sender == account);
        _;
    }
    function query(bytes memory data, function(bytes memory) external callback) public
    {
        requests.push(Request(data, callback));
        // This generates a public event on the blockchain that will notify clients
        emit NewRequest(requests.length - 1);
    }
    // invoked by outside world
    function reply(uint256 requestID, bytes memory response) public onlyBy(knownSource)
    {
        requests[requestID].callback(response);
    }
}
// Oracle consumer
contract OracleConsumer {
    Oracle oracle_addr = Oracle(address(0x4321)); // known contract oracle
    modifier onlyBy(address account) { 
        require(msg.sender == account);  _; 
    }
    function updateExchangeRate() public {
        oracle.query("USD", this.oracleResponse);
    }
    function oracleResponse(bytes memory response) public onlyBy(address(oracle)) {
        // do something with response
    }
}
