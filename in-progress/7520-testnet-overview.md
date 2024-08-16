# [TestNet Design Overview](https://github.com/AztecProtocol/aztec-packages/issues/7520)

|                      |                                  |
| -------------------- | -------------------------------- |
| Owners               | @just-mitch @LHerskind @Maddiaa0 |
| Approvers            | @charlielye @joeandrews          |
| Target Approval Date | 2024-08-16                       |

This document is a system design overview of what is to be delivered as the TestNet, focusing on networks, L1 interactions, governance, and economics.

A fully functional test network is expected to be delivered by Dec 2, 2024. This network will be a publicly available, but with no guarantees of security or stability.

The deployed network will be referred to as "TestNet".

Thus, in the immediate term, Aztec Labs and/or the Aztec Foundation (once set up) will be coordinating the operation of the following networks:

- Staging: a private network for testing and development
- DevNet: a public network for app developers with a centralized sequencer and prover
- Spartan: a public network for infrastructure providers with permissioned sequencers and provers

By December 16, 2024, these will be consolidated into:

- Staging: a private network for testing and development
- TestNet: a public network with permissionless sequencers and provers

The objective of this document is to:

- outline engineering's current understanding of what will be built
- pose open questions that need to be resolved, either internally or with the community or external researchers

**Note:** Most of the components below will have their own design documents.

## Overview

The Aztec Network is a privacy-focused, general-purpose Layer 2 network built on Ethereum. It will use zero-knowledge client-side proofs to enable private, programmable transactions, a VM to enable verified public computation, and a rollup architecture to scale. Aztec will be designed to be permissionless and decentralized, while maintaining sound economics, governance, as well as turing complete functionality for application developers to build in any applicable compliance requirements.

## L1

L1 is Ethereum Sepolia.

## Network L1 Deployments

A deployment of the Aztec Network includes several contracts running on L1.


### TST Contract

The Test Token (TST) will be an ERC20 token that will be used to pay for transaction fees on the Aztec Network.

It will also used on L1 as part of the validator selection process.

Protocol incentives are paid out in TST.

A canonical bridge will allow bridging TST from L1 to L2.

TST bridged through the canonical bridge is exclusively used to pay transaction fees; it cannot be transferred to other users on L2.

The TST contract will be immutable.

### Incentives Contract

The Incentives contract will be responsible for minting TST.

Only the owner of the Incentives contract can mint TST.

It has a rate limiter on minting.

The Incentives contract will be immutable.

### Governance Contract

The Governance Contract owns the Incentives contract.

TST holders can lock their TST in the Governance Contract to vote on proposals.

Proposals can only be submitted by the PendingProposals Contract.

Proposals must garner X% of the total locked TST to be ratified.

There will be a time delay between ratification and execution.

### Registry Contract

The Registry Contract will be able to keep track of the current/canonical and historical Instances.

An Instance will be comprised of:
- A Rollup Contract, which is the main contract that handles the rollup of transactions.
- A Data Availability Oracle, which is responsible for answering if the preimage of commitments have been made available.
- An Inbox, responsible for receiving messages from L1 and making them available L2.
- An Outbox, responsible for receiving messages from L2 and making them available on L1.

### Rollup Contract

The initial Rollup Contract will require holders of TST to stake their tokens to become validators.

The initial Rollup Contract will maintain a balance of TST to be used for rewards.

### PendingProposals Contract

The Proposals Contract keeps track of governance proposals and votes.

It watches for proposal signals in the Registry's canonical Instance.

When M of the previous N blocks contain the same proposal, it is submitted to Governance.

## Forced Inclusions

Deployments will have a mechanism for forced inclusions of transactions in the canonical chain.

### Open Questions

- How does it work?
- Can this mechanism be tied to the based sequencing mechanism?

## Aztec Node

Aztec Labs will provide a reference implementation of the Aztec Node, which will be used to run the Aztec Network.

It will have 3 primary modes of operation:

- Proposer/Validator: responsible for proposing new blocks and validating them
- Prover: responsible for orchestrating the creation of various proofs
- Full Node: follows along, responsible for propagating transactions and blocks

The Aztec Node will have a web interface for monitoring key metrics.

## Chains, slots, and epochs

There will be three chains in the Aztec Network:

- The Pending Chain
- The Proven Chain
- The Finalized Chain

All three chains will be effectively managed by the Aztec Node and the L1 contracts, and will have different guarantees.

Time will be divided into slots, which will be grouped into epochs.

Each slot will have a proposer, who is responsible for proposing a block of transactions.

Each epoch will have a set of validators, who add economic security to the Pending Chain by providing signatures on proposed blocks; ultimately the Pending Chain is a UX feature that allows users to see their transactions with _some guarantee_ before they are proven.

### Open Questions

- How long should a slot be?
- How long should an epoch be?

## The Pending Chain

The purpose of the pending chain is to reduce the perceived latency of transactions: it allows clients to observe transactions that have been proposed, but the proof has not yet been made available.

The proposer for a slot produces a list of transaction objects either by

- selecting them from the L2 mempool,
- or receiving a list from a builder.

The proposer gossips to the validators:

- A signature showing it is the current proposer
- The list of transaction objects

Validators check that the proposer is the current proposer, and verify the private kernel proofs of the transaction objects.

They then create a signature over the list of transaction objects.

Once the proposer has collected enough signatures, it submits the signatures and TxObjects to the rollup contract dedicated to advancing the pending chain.

The next proposer will watch L1, execute the constituent transactions (possibly getting them from a peer) and produce the implied L2 header of the **previous/published** block *before* it then selects the TxObjects that will form its block.

In the course of execution, the proposer may find that a transaction is "invalid", i.e., the private kernel proof is cannot verify. 

Ultimately, the proposer who included the invalid transaction will be penalized.

### Open Questions

- Do we need to do optimistic signature verification?
- How many signatures are required?
- How will the proposer of the invalid transaction be charged?

## The Proven Chain

The purpose of the proven chain is to verify a zero-knowledge proof that attests to the correctness of the transactions in the pending chain.

It is a prefix of the pending chain.

The proposer named in the first slot in an epoch has monopoly rights on proving the previous epoch.

The proof of epoch `i` must be submitted within a certain number of L1 blocks after the end of epoch `i`.

If this does not happen, there is an "open challenge period" where anyone can submit a proof of the epoch.

If no proof is submitted the epoch is considered invalid; the pending chain is rolled back to the last proven epoch.

The proposers must coordinate payment and proving out of protocol.

Some users may coordinate with prover marketplaces, but the Aztec Node will come with the ability to "self-prove" an epoch.

### Open Questions

- Is a prover commitment bond needed in-protocol?
- How do proving marketplaces integrate?
- What is the timeliness requirement for the proof submission?
- What is the open challenge period?
- Under what conditions can the pending chain be rolled back?
- Is "steal your funds" ever possible?

## Based Sequencing

As a safety mechanism, all deployed instances will support a "based" sequencing mode that allows blocks to be added to the pending/proven chain without the need for L2 validators.

### Open Questions

- How does it work?
- What are the circumstances for using based sequencing?

## The Finalized Chain

The purpose of the finalized chain is to provide a final, immutable (up to Casper FFG) record of the state of the Aztec Network.

It is a prefix of the proven chain, and blocks naturally move from the proven chain to the finalized chain as proofs become finalized in the eyes of L1.

## Node Types

All the nodes participate in the peer-to-peer (p2p) network but with varying capacity.

1. **Light Node**:
   - Download and validate headers from the p2p network.
     - Sometimes an "ultra-light" node is mentioned, this is a node that don't validate the headers it receive but just accept it. These typically are connected to a third party trusted by the user to provide valid headers.
   - Stores only the headers.
   - Querying any state not in the header is done by requesting the data from a third party, e.g. Infura or other nodes in the p2p network. Responses are validated with the headers as a trust anchor.
   - Storage requirements typically measured in MBs (< 1GB).
   - Synchronization time is typically measured in minutes.
2. **Full Node**:
   - Receive and validate blocks (header and body) from the p2p network.
   - Stores the complete active state of the chain
   - Typically stores recent state history (last couple of hours is common)
   - Typically stores all blocks since genesis (some pruning might be done)
   - Can respond to queries of current and recent state
   - Storage requirements typically measured in GBs (< 1TB)
   - Synchronization time is typically measured in hours/days.
3. **Archive Node**:
   - Receive and validate blocks (header and body) from the p2p network
   - Stores the full state history of the chain
   - Stores all blocks since genesis
   - Can respond to queries of state at any point in time
   - Storage requirements typically measured in TBs
   - Synchronization time is typically measured in hours/days.

### Open Questions

- What kind of "watcher" role can full nodes play?

## Prover Nodes

Prover nodes will receive information from proposers and will be responsible for creating proofs, and posting them to L1.

### Open Questions

- What is the interface that proposers will use to communicate with prover nodes?
  - Do they need one other than L1?

## Proposer/Validator Selection

As noted above, the initial Rollup contract will allow holders of TST to stake a set amount of their tokens to become validators.

Much of Ethereum will be mimicked in that one user can have multiple validators.

A randao will be used to select a committee from the validator set for each epoch.

Each slot in an epoch will be randomly assigned to a validator in the committee.

### Open Questions

- How resistant is this to censorship?
- How expensive is it to run?
- How can reward be distributed?
- What are the slashing conditions?
- Probability/severity/cost of different attacks based on the power of attacker (1%, 5%, 10%, 20%, 33%, 50%, 67% of stake)
- Time to detect and react to a safety breach?
- What is the marginal cost/benefit of an extra validator in the set/committee?

## Fees

Every transaction in the Aztec Network has a fee associated with it. The fee is payed in TST which has been bridged to L2.

Transactions consume gas. There are two types of gas:

- L2 gas: the cost of computation
- DA gas: the cost of publishing/storing data

When a user specifies a transaction, they provide values:

- maxFeePerL2Gas: the maximum fee they are willing to pay in TST per unit L2 gas
- maxFeePerDAGas: the maximum fee they are willing to pay in TST per unit DA gas
- l2GasLimit: the maximum amount of L2 gas they are willing to consume
- daGasLimit: the maximum amount of DA gas they are willing to consume

Thus, the maximum fee they are willing to pay is:

- maxFee = maxFeePerL2Gas * l2GasLimit + maxFeePerDAGas * daGasLimit

There is an additional pair of parameters to support complex flow such as fee abstraction:

- l2TeardownGasLimit: the maximum amount of L2 gas they are willing to consume for the teardown of the transaction
- daTeardownGasLimit: the maximum amount of DA gas they are willing to consume for the teardown of the transaction

Both of these values are used to "pre-pay" for the public teardown phase of the transaction.

Each L2 block has a fixed L2 gas limit and a DA gas limit.

There will be an in-protocol mechanism for updating the `feePerL2Gas` and `feePerDAGas` values.

### Open Questions

- How will the user figure out a fitting value for `maxFeePerL2Gas` and `maxFeePerDAGas`
- How can it be ensured that the cost of proving is covered by L2 gas?
- How will L1 figure out fitting values for `feePerL2Gas` and `feePerDAGas`, such that costs are correctly passed back to the users?

## Pending Block Rewards

No rewards are planned for pending blocks, as only the finalization of blocks should be incentivized.

## Proven Block Rewards

There will be rewards for proven blocks.

These will be in addition to the transaction fees paid by users.

### Open Questions

- How much should proven blocks be subsidized?
- How much should the protocol retain for future development?
- Historical proposers and validators should be rewarded. How can this be done in a way that is not extremely costly?

## Transaction Lifecycle

The executable code of a transactions follows the following lifecycle:

1. Locally, in private:
   1. Setup
   2. App Logic
2. On L2, in public:
   1. Setup
   2. App Logic
   3. Teardown

If the private portion fails, the transaction is not submitted to L2.

If the public portion fails in the setup phase, the transaction is invalid, and discarded.

If the public portion fails in the app logic or teardown phase the side effects from the failing stage are discarded but the transaction is still valid. Users can simulate their transactions ahead of time and not submit them if they fail.

### Open Questions

- How painful is it for sequencers to whitelist public setup code?

## Data Availability

Ethereum blobs will be used to publish TxObjects and proofs.

A layer of abstraction will be provided to allow for similar DA solutions (e.g. EigenDA, Celestia).

### Open Questions

- What are the security assumptions the DA solution must satisfy?
- What are the throughput and latency requirements for the DA solution?

## Penalties and Slashing

There will be penalties for proposers and provers who do not fulfill their duties.

### Open Questions

- Under what conditions should actors be slashed?
  - committee members
  - proposers
  - provers
- What is require to convince L1 that the conditions are met?
- What is the "cost" of an enforcement action? e.g., if tiny penalty it might not be worth to enforce it.
- What are the penalties for proposers and provers?
- How can it be ensured that the penalties are fair?
- What should be burned, and what should be distributed?
- Expected annual return for validators (mean, median)?

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
