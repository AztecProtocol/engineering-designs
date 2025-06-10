|                      |                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------- |
| Owners               | @PhilWindle                                                                                   |
| Approvers            | @just-mitch @alexghr @spalladino  @Maddiaa0                                                   |
| Target Approval Date | 2025-06-10                                                                                    |


## Executive Summary

This design attempts to define a more effective protocol for the retrieval of missing transactions from the network.


## Introduction

There is an outstanding problem with the block building protocol that we have no data availability solution. Node's mempools will naturally diverge and it is likely, particularly at higher transaction througputs that validators and provers won't have access to the transactions included in blocks proposed by the block proposer.

The codebase currently contains a request/reponse mechanism for retrieving these transactions but it has not proven very effective. This design aims at improving on it.

## Transaction Lifecycle

For the purpose of network participants, transactions have a rough lifecycle.

1. The transaction is stored as pending within the local mempool. During this time it may be subject to eviction, based on rules local to the node. We will refer to this state as PENDING.
2. The transaction is included in a block proposal. At this point the transaction should not be evicted as it may be required for block validation. We will refer to this state as PROPOSED.
3. The transaction is included in a mined block. All mined transactions are stored for a period of time. We will refer to this state as MINED.
4. The transaction's block is proven or pruned. We will refer to this state as EXPIRED.

Block proposals follow a similar lifecycle with the exception there is no such thing as a PENDING state for proposals.

If a block proposal does not result in a mined block, the transactions within it will revert to PENDING.

## Requirements

The requirements of validators are that transactions can be retrieved quickly. The transactions need to be retrieved and the block needs to be re-executed in time for an attestation to be produced. Provers also require transactions for re-execution, their timeliness requirements are less strict as they essentially have 1 - 2 epochs to produce the required proofs.


## Current Approach

Every node on the network subscribes to block proposals. Upon receiving a block proposal, the node will instruct it's transaction pool to mark the transaction hashes as PROPOSED, non-evictable. The node will then make an attempt to request any missing transactions from it's peers on the network. All PROPOSED hashes are removed from the pool when any block is mined.

The node makes a number of 'rounds' of requesting transactions. Each round sees it select a random subset of peers and ask each peer for a subset of missing transactions. Timeouts are specified for each round and globally. The peer that sent propagated the proposal to the peer (note: not the proposer of the block) is always included in the peer subset.

The timeout values are arbitrarily set to 2 seconds and 8 seconds currently. The max number of peers selected for each round is a function of the number of transactions required.

A request for a transaction is singular, 1 tx at a time. Requests to a given peer are performed serially so at any given time a single peer is only asked for a single transaction. Each request is a unique dial, request/response and hang-up operation.

## Proposed approach

As before, every node on the network subscribes to block proposals and marks transaction hashes so as not to evict those transactions from the pool. Transaction hashes remain marked until the end of the slot after the slot in which they were PROPOSED. This avoids race conditions where a proposal for slot n + 1 arrives before a node synced the block for slot n. The syncing of the block currently would remove the protection for transactions in the new block proposal.

The `TxCollector` module will be modified to become a longer running task that can be thought of as permamnently making attempts to retrieve transactions from the network. It will dial and hold connections/streams to all connected peers. As stream/connection events happen it will re-attempt to establish connectivity and maintain available streams.

Upon receipt of a block proposal, the `TxCollector` will be notified of the proposal and the transactions that need to be retrieved. It will continue to perform a series of message exchanges with all peers until the transactions are no longer required.

Reason for the transactions no longer being required are:

1. The proposal never made it into a mined block and the following slot has passed. The transaction transitioned back to PENDING.
2. The block and it's transactions become EXPIRED.
3. The transactions have been retrieved.

### Block Tx Request/Response

Instead of randomly selecting peers to query with random tx requests, the node will make frequent message exchanges with all of it's peers, these messages will be small and sent over previously established streams reducing latency.

We introduce two intervals, the `proposedRequestInterval` and the `minedRequestInterval`, typically say 500ms and 2000ms respectively. 

Every `proposedRequestInterval`, the node makes an evaluation as to which block proposals it still requires transactions for and when it last enquired about a proposal. Queries will be made for proposals that are PROPOSED at this interval (provided txs are still required), proposals that are MINED will be queried at the less frequent `minedRequestInterval`.

Peers are queried using `BlockTxRequests` messages.

```
type BlockTxRequest = {
  slotNumber: number,
  blockHash: Buffer, // 32 byte hash of the proposed block header
}

type BlockTxRequests = {
  requests: BlockTxRequest[]
}
```

Upon receipt of a `BlockTxRequests` the peer will respond with a `BlockTxResponses`.

```
type BlockTxResponse = {
  slotNumber: number,
  blockHash: Buffer, // 32 byte hash of the proposed block 
  blockAvailable: boolean; // Whether the peer has the block available
  txIndices: Buffer, // BitVector indicating which txs from the proposal are available at the peer
}

type BlockTxResponses = {
  responses: BlockTxResponse[]
}
```

The frequent exchange of these messages enables nodes to build up mappings of where in their sets of peers transactions are available. These mappings will change rapidly as peers also implement the same transaction retrieval protocol.

### Tx Request/Response

Transactions are requested in batches using the `TxRequest` message.

```
type TxRequest = {
  slotNumber: number,
  blockHash: Buffer, // 32 byte hash of the proposed block
  txIndices: Buffer, // BitVector indicating which txs from the proposal are requested
}
```

Using the mapping generated using the Block Tx Request/Response message exchange we intelligently request transactions from selected peers.

1. Only make a single request to a peer at a time.
2. Limit the number of transactions requested in a single request to a configurable `batchSize`.
3. Allocate txs to peers such that we optimally retrieve all txs in the minimum number of requests and asking for the minimum number of txs from any given peer.

Only making a single request to a peer with a limited number of transactions prevents a node from simply requesting all available transactions from the first peer to respond. Instead we should aim to spread the load as much as possible.

