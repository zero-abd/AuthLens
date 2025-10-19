// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VideoAuth {
    mapping(bytes32 => address) public hashes;
    event HashStored(address indexed uploader, bytes32 indexed videoHash);

    function storeHash(bytes32 _videoHash) public {
        require(hashes[_videoHash] == address(0), "Error: This video hash has already been registered.");
        hashes[_videoHash] = msg.sender;
        emit HashStored(msg.sender, _videoHash);
    }

    function verifyHash(bytes32 _videoHash) public view returns (bool, address) {
        address uploader = hashes[_videoHash];
        bool exists = (uploader != address(0));
        return (exists, uploader);
    }
}