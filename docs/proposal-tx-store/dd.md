# Intro

Unlike Ethereum, Aztec transactions are significant in size and take a relatively large amount of computation to verify. Consequently, it is infeasible to publish them over the P2P network along with the block proposals.

This presents a problem: what if an insufficient number of nodes/validators have the transactions available for re-execution?

## Current Solution

The solution to date is multi-faceted.

1. Transactions are gossiped across the entire network using libp2p's gossipsub.
2. Nodes use a system of requesting transactions they don't have from peers.
3. The design for Supernodes adds the ability for validators to have access to very high quality peers for the purpose of reliable gossip and req/response.

Whilst the protocol and node software makes a best effort to achieve reliable tx retrieval, no solution is guaranteed. It is ultimately the responsibility of the committee to ensure that transactions are available and it is specifically in the interests of the block proposer that blocks can be executed.

## Proposed Changes

To further enhance the availability of transactions for proposal execution. An optional field is added to the block proposals contaning a url with which nodes can retrieve any required transactions.

The process would work as follows:

1. Block Building 

The proposer builds a block and for each transaction, places the transaction (both the request and the proof) into a filesystem.

2. Block Proposal

An additional, optional field is added to the `BlockProposal` which the proposer populates with the base url of the file store.

```TS
export class BlockProposal {
  //...Current fields
  public readonly url?: string;
}
```

Transactions should be retrievable at e.g. `${url}/${txhash}`.

3. Tx Retrieval

Any node that finds it is missing transactions from the proposal would have the option, in addition to performing req/resp against it's peers, of attempting to read the transactions from the store. Transactions read from the store would still need to be verified like any others.

4. Cleanup

The configuration parameter `TX_STORE_SLOT_DURATION` is provided and determines the number of slots that transactions are made available for. Allowing additional time beyond the slot of the block proposal would enable e.g. provers more time to retrieve the transactions if neccessary.