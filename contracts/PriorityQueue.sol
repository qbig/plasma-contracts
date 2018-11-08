pragma solidity ^0.4.0;

import "./PriorityQueueLib.sol";

/**
 * @title PriorityQueue
 * @dev A priority queue implementation
 */
contract PriorityQueue {
    using PriorityQueueLib for PriorityQueueLib.Queue;

    /*
     *  Modifiers
     */

    modifier onlyOwner() {
        require(queue.isOwner());
        _;
    }

    /*
     *  Storage
     */

    PriorityQueueLib.Queue queue;

    /*
     *  Public functions
     */

    constructor()
        public
    {
        queue.init();
    }

    function insert(uint256 k)
        onlyOwner
        public
    {
        queue.insert(k);
    }

    function minChild(uint256 i)
        public
        view
        returns (uint256)
    {
        return queue.minChild(i);
    }

    function getMin()
        public
        view
        returns (uint256)
    {
        return queue.getMin();
    }

    function currentSize()
        public
        view
        returns (uint256)
    {
        return queue.getCurrentSize();
    }

    function delMin()
        onlyOwner
        public
        returns (uint256)
    {
        return queue.delMin();
    }
}
