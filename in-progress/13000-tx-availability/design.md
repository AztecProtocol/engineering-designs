|                      |                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------- |
| Owners               | @PhilWindle                                                                                   |
| Approvers            | @Maddiah @alexghr @spalladino                                                              |
| Target Approval Date | 2025-05-23                                                                                    |


## Executive Summary

This design attempts to solve the problem of ensuring that txs are made available to the network.


## Introduction

There are 3 primary actors on the Aztec Network.

1. Full Nodes, these participate in gossiping and usually provide RPC endpoints for clients.
2. Validators, these are full nodes that additionally propose and validate new blocks. Validators are organised into committees of 48. Every slot (currently 3 ETH slots) a committee member proposes a block and sends this proposal to the rest of the committee for attestation.
3. Provers, these are full nodes that also orchestrate the proving of epochs (batches of previously proposed blocks).

The network needs to ensure that txs are made available to validators and provers. From this we can derive a set of requirements:

1. Proposers are assumed to already have access to the transactions they are including in the block.
2. Validators need to have access to the transactions to re-execute and attest to the block. This needs to be achieved in a short period of time, validators have in the order of 10 seconds to attest to a block.
3. Provers also require transactions for re-executing and proving the epoch. This is less time critical as proving is performed over the course of 2 epochs.
4. Additionally, both validators and provers need to verify the proofs that accompany the transactions, these proofs dominate the size of the transaction payload.
5. From a network perspective, we are satisfied with 66% of validators successfully re-executing and attesting to a block. The network only requires 1 prover to submit a proof of an epoch.

When it comes to hardware and bandwidth requirements, it is desirable for people to be able to operate as validators with a single consumer grade machine and home broadband connectivity with potentially limited upload bandwidth. Provers can be expected to have significantly more resources, these are likely to be professional/institutional organisations.

## Current Architecture

The principal method by which transactions are distributed around the network is via the gossipsub protocol. Those transactions are then stored in a node's local database and will be subject to eviction based on their priority fee and the node's configuration around the maximum size of it's transactions pool. There are a number of reasons why at any given point in time a node may not have a transaction available, namely:

1. Being offline/disconnected at the time the transaction was gossiped
2. Having limited transaction storage causing transactions to be evicted
3. Imperfect gossiping
4. Client software using varying strategies for transaction eviction
5. Bugs in the implementation of the transaction pool

In addition to the gossipsub protocol, there are other mechanisms used to retrieve transactions:

1. Request/Response. Validators and provers will randomly select subsets of their total peers and directly request the transactions that they are missing. This is done repeatedly over a period of rounds until the transaction is found or an arbitrary time limit is reached. Nodes are careful when using this so as to not be too aggressive in their requests. Nodes employ peer-scoring techniques to rate limit peers that are requesting too much data. As a result, request-response is not a completely reliable mechanism for transaction retrieval.
2. Prover Coordination. Provers can be configured with any number of http urls that they can use to retrieve transactions. This enables provers to run a number of additional nodes on the network for the purpose of increasing their chances of receiving everything they require.

## Proposed Solution

Gossiping is already very effective at transaction propagation and it is assumed that with further reductions in proof size/increases in bandwidth availability this will continue to be the case. However, due to the reasons outlined above, we have to assume that there will be instances of nodes not having the transactions they require.

The ultimate solution would be to do as Ethereum does and bundle the transactions with the block proposal. This would ensure that everyone who requires the transactions would have them. However, this is not feasible. Transactions are approximately 60KB compressed. A block proposal containing transactions at a rate of 10 TPS will contain 360 transactions = ~22MB of data. 

Our usage of Gossipsub works such that:

1. The original publisher of a message sends to all peers. This number is configurable but likely to be no less than 50.
2. All other peers propagate to a subset, around 5/6 peers.

Therefore, a proposer would need to send 50 * 22 MB = 1.1 GB of data and all other peers would need to send 5 * 22 MB = 110 MB. This would result in validators simply not having time to attest to block proposals.

Therefore, we propose a solution that adds additional layers/protocols and enhancements to the current gossipsub + request/response methods encapsulated with a new TxRetrieval module. TxRetrieval will continuously work to retrieve all transactions specified as part of block proposals until either the transaction has been retrieved or the transaction is not included in a mined block. This latter case is identifed by the publishing of a block that does contain the transaction and where the transaction has not been included in a prior mined block.

### Request/Response from proposal propagater

Upon receipt of a block proposal where the receiving peer P does not have all required transactions, P will start a request reponse process but will more aggresively target the peer propagating the block proposal. That is to say, that each round of peer sampling will always include the propagating peer. The block proposal will be propagated further immediately, regardless of whether P is missing transactions or not. This ensures that the proposal is not delayed.

To mitigate peers from being targetted by DOS attacks, we can attach the block proposal ID to any requests for transactions. The peers being asked can then verify that it is a known, recent proposal. Additionally, the peer can choose to only accept these requests from peers that it gossiped the block to in the first place and can limit the number of such requests that it is willing to service.

Targeting the propagating peer in this way ensures that the transaction 'should' propagate throughout the network albeit at a potentially slower rate than gossiping. Every level of propagation requires a round trip of request/response. 

We don't wait for each level of propagtion to retrieve the transactions as doing so would delay the block proposal. It is possible (even likely) that a sufficient number of validators already have the transactions and can execute immediately.

### Request/Response directly from proposer

Performing request/response more aggresively from the propagator should further increase the likelihood of transactions being generally available to all peers. However, if this is found to still be insufficient then we propose a method of requesting directly from the proposer. This would only be an option for committee members.

Validators would be required to post their Ethereum public key as part of joining the validator set. The proposer can then optionally setup an auth'd endpoint through which it will serve requests for transactions in the block proposal. The details of this endpoint would be encrypted with each committee member's public key and included in the block proposal. The proposer has complete control over this endpoint enabling them to protect themselves against potential DOS attacks by malicious committee members.

### Make prover coordination urls universal

As a leftover from the previous method of prover coordination, provers have additional configuration allowing them to request transactions from other nodes via http. This can be made a universal option for all nodes and incorporated into the TxRetrieval workflow.

### Increasing prover transaction pool requirements

Provers are assumed to be organisations with access to considerable hardware resources and bandwidth capabilities. It is not unreasonable for them to:

1. Run multiple full nodes in addition to the prover node.
2. Configure every node with a very large transaction pool size, significantly reducing the transaction eviction rate.
3. Configure every node to have a high peer count, increasing the likelihood of request/response success.

### Centralised transaction storage for provers

The committee is ultimately responsible for epochs being proven so it is in their interests for transactions to be made available to provers. This may encourage some/all validators to simply push transaction data to a centralised storage service for a period of time after each block is mined allowing provers access.