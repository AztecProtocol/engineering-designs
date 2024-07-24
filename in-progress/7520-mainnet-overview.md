# [MainNet Design Overview](https://github.com/AztecProtocol/aztec-packages/issues/7520)

|                      |            |
| -------------------- | ---------- |
| Owners               |            |
| Approvers            |            |
| Target Approval Date | 2024-08-06 |


This document is a system design overview of what we want to deliver as our MainNet release, focusing on networks, L1 interactions, governance, and economics.

We will deliver a fully functional network by Dec 16, 2024. This network will be a publicly available, but with no guarantees of security or stability.

The deployed network will be referred to as "TestNet", but it will reflect the design of the coming "MainNet".

Thus, in the immediate term, Aztec Labs will be running three networks:

- Staging: a private network for testing and development
- DevNet: a public network for app developers with a centralized sequencer and prover
- Sequencer/Prover TestNet (SPRTN): a public network for infrastructure providers with permissioned sequencers and provers

By 2024-12-16, these will be consolidated into:
- Staging: a private network for testing and development
- TestNet: a public network with permissionless sequencers and provers

The objective of this document is to:
- outline engineering's current understanding of what will be built
- pose open questions that need to be resolved, either internally or with the community or external researchers

## Overview 

The Aztec Network is a privacy-focused, general-purpose Layer 2 network built on Ethereum. It uses zero-knowledge client-side proofs to enable private, programmable transactions, a VM to enable verified public computation, and a rollup architecture to scale. Aztec is designed to be permissionless and decentralized, while maintaining sound economics, governance, and compliance.

## L1

L1 is Ethereum Sepolia. 

## Top Level Governance

There is a Top Level Governance (TLG) contract, and an Aztec Token (AZT) contract deployed on L1. 

Neither contract is tied to any specific deployment of the Aztec Network.

The TLG is a minter of the Aztec Token.

Holders of AZT will be able to submit proposals to the TLG, which will be voted on by AZT holders.

## Network Deployments

A deployment of the Aztec Network includes several contracts running on L1.

Each Deployment has a Registry, and a Rewards contract.
The Registry points to the current/canonical and historical "Instances" of the Deployment.

An Instance of a Deployment includes:
- A Rollup Contract, which is the main contract that handles the rollup of transactions.
- A Data Availability Oracle, which is responsible for providing data published to our DA solution.
- An Inbox, responsible for receiving messages from L1 and making them available L2.
- An Outbox, responsible for receiving messages from L2 and making them available on L1.

After the deployment is created, a proposal is submitted to the TLG, requesting funding of the Rewards contract.

The Registry contract also describes how the Deployment can be governed, and will vary depending on the Deployment.

There are two deployments as part of TestNet:
- Alpha: `testnet-alpha`
- Beta: `testnet-beta`

The Alpha deployment will be governed by the Aztec Labs team.
The Beta deployment will be governed by the TLG.

## Deployment Upgrades

Deployments can issue new Instances to upgrade the network.

For Alpha, the Aztec Labs team will instruct the Registry to point to the new Instance. Upgrades will occur after an execution delay of 1 hour.

For Beta, a proposal will be submitted to the TLG to instruct the Registry to point to the new Instance. There will be a setup period of 1 day, a voting period of 3 days, and an execution delay of 2 days.

In both cases, the new Instance will be instantiated with the state of the old Instance.

### Open Questions
- What happens to bridged assets during an upgrade? What options do users have?

## Forced Inclusions

Deployments will have a mechanism for forced inclusions of transactions in the canonical chain.

### Open Questions
- What are the requirements for a forced inclusion?
- Is there any DoS risk?
- Is this influenced by the sequencer selection process?

## The Aztec Token

The Aztec Token (AZT) is an ERC20 token that is used to pay for transaction fees on the Aztec Network.

It is also used on L1 as part of the validator selection process.

Protocol incentives are paid out in AZT.

AZT is bridged from L1 to L2 using a trusted bridge.

Once on L2, AZT is exclusively to used to pay transaction fees; it cannot be transferred back to L1 or transferred to other users.

## Compliance

### Open Questions
- What are the compliance requirements for the Aztec Network?


## Aztec Labs Node

Aztec Labs will provide a reference implementation of the Aztec Node, which will be used to run the Aztec Network.

It will have 3 primary modes of operation:
- Proposer/Validator: responsible for proposing new blocks and validating them
- Prover: responsible for orchestrating the creation of various proofs
- Full Node: follows along, responsible for propagating transactions and blocks

The node will have a web interface for monitoring key metrics.


## Chains, slots, and epochs

There are two chains in the Aztec Network:
- The Pending Chain
- The Proven Chain
- The Finalized Chain

All three chains are effectively managed by the Aztec Node and the L1 contracts, and have different guarantees.

Time is divided into slots, which are grouped into epochs.

Each slot has a proposer, who is responsible for proposing a block of transactions.

Each epoch has a set of validators, who are responsible for validating the blocks proposed by the proposers.

### Open Questions
- Would a "pure L2" chain help us achieve our goals?
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

Validators check that the proposer is the current proposer.
They then build an L2 block by executing the transaction objects, and sign the resulting L2 block header.

Once the proposer has seen enough signatures, they can submit the L2 block to L1.

The proposer submits the block header as calldata to a function on the rollup contract dedicated to advancing the pending chain.

### Open Questions
- How many signatures are required?
- Does the need to execute the transaction objects create too much of a burden on validators?
- If we cannot execute the transaction objects, how does the rest of the system work?
- How do costs of signature verification change with the sequencer selection process?

## The Proven Chain

The purpose of the proven chain is to verify the correctness of the transactions in the pending chain.

It is a prefix of the pending chain.

The first block in an epoch must contain a commitment on behalf of the proposer to proving the current epoch.

This is done by placing a large "prover commitment bond" in the block.

The proof of epoch `i` must be submitted within a certain number of L1 blocks after the end of epoch `i`.

If this does not happen, there is an "open challenge period" where anyone can submit a proof of the epoch, and claim part of the prover commitment bond.

If no proof is submitted, the proposer loses the bond, and the epoch is considered invalid; the pending chain is rolled back to the last proven epoch.

The proposer who posts the prover commitment bond must to coordinate payment and proving out of protocol.

Some users may coordinate with prover marketplaces, but the Aztec Node will come with the ability to "self-prove" an epoch.

### Open Questions
- How large should the prover commitment bond be?
- How do proving marketplaces integrate?
- What is the timeliness requirement for the proof submission?
- What is the open challenge period?
- Under what conditions can the pending chain be rolled back?
- Is "steal your funds" ever possible?

## Based Sequencing

As a safety mechanism, all deployed instances will support a "based" sequencing mode that allows blocks to be added to the pending/proven chain without the need for L2 validators.

### Open Questions
- What are the circumstances for using based sequencing?

## The Finalized Chain

The purpose of the finalized chain is to provide a final, immutable (up to Casper FFG) record of the state of the Aztec Network.

It is a prefix of the proven chain, and blocks naturally move from the proven chain to the finalized chain as proofs become finalized in the eyes of L1.

## Full Nodes

Full nodes sit on the P2P network and are responsible for:
- Propagating transactions
- Propagating proposals
- Propagating attestations

They can validate proposed L2 blocks they see, and verify proofs.

### Open Questions
- What kind of "watcher" role can full nodes play?


## Prover Nodes

Prover nodes will receive information from proposers and will be responsible for creating proofs, and posting them to L1.

### Open Questions
- What is the interface that proposers will use to communicate with prover nodes?

## Proposer/Validator Selection

There will be a sybil-resistant mechanism for selecting the validators for each epoch.

There will be a fair mechanism for assigning individual validators to be proposers for slots.

We see two broad options for selecting validators:
- A trustless system where validators are selected based on staked AZT
- A system where validators are voted on by AZT holders

Over the coming weeks we will be working with external researchers and the community to decide which system is best.


### Open Questions

The main questions we need to answer for each system are:
- How resistant is this to censorship?
- How expensive is it to run?
- How can we distribute rewards?
- How do we enumerate all possible slashing conditions?
- How much malicious AZT can we tolerate before we lose safety/liveness?
- How large should the validator set be?
- How many validators should be selected per epoch?

## Fees

Every transaction in the Aztec Network has a fee associated with it. The fee is payed in AZT which has been bridged to L2.

Transactions consume gas. There are two types of gas:
- L2 gas: the cost of computation
- DA gas: the cost of publishing/storing data

When a user specifies a transaction, they provide values:
- maxFeePerL2Gas: the maximum fee they are willing to pay in AZT per unit L2 gas
- maxFeePerDAGas: the maximum fee they are willing to pay in AZT per unit DA gas
- l2GasLimit: the maximum amount of L2 gas they are willing to consume
- daGasLimit: the maximum amount of DA gas they are willing to consume

Thus, the maximum fee they are willing to pay is:
- maxFee = maxFeePerL2Gas * l2GasLimit + maxFeePerDAGas * daGasLimit

There is an additional pair of parameters to support complex flow such as fee abstraction:
- l2TeardownGasLimit: the maximum amount of L2 gas they are willing to consume for the teardown of the transaction
- daTeardownGasLimit: the maximum amount of DA gas they are willing to consume for the teardown of the transaction

Both of these values are used to "pre-pay" for the public teardown phase of the transaction.

Each L2 block has a fixed L2 gas limit and a DA gas limit.


### Open Questions

- Can we ensure that the cost of proving is covered by L2 gas?
- How do we pass back L1 compute and DA costs back to users?
   - In an elected proposer system, can proposers simply set the fee?
   - In a trustless proposer system, how do we ensure that the fee is set based on the price of eth and the current exchange rate to AZT? Do we need an enshrined price oracle?

## Pending Block Rewards

We do not plan to have rewards for pending blocks, as we only want to incentivize the finalization of blocks.

## Proven Block Rewards

We will have rewards for proven blocks.

These will largely be funded by the transaction fees.

### Open Questions

- How much do we need to subsidize proven blocks?
- How much should the protocol retain for future development?
- How do distribution of rewards work w.r.t. sequencer selection?
  - In a trustless proposer system, we likely need to reward historical proposers and validators. How do we do this in a way that is not extremely costly?
  - In an elected proposer system, can we simply evenly distribute rewards to the committee?

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

If the public portion fails in the app logic or teardown phase the side effects from the failing stage are discarded but the transaction is still valid.

### Open Questions
- How painful is it for sequencers to whitelist public setup code?
- If validators don't re-execute and thus sign headers, what is the engineering fallout for needing to deal with invalid transactions? How does the proposer pay for this?

## Data Availability

We will use ethereum blobs to publish TxObjects and proofs.

We will provide a layer of abstraction to allow for similar DA solutions (e.g. EigenDA, Celestia).

### Open Questions
- What are the throughput and latency requirements for the DA solution?

## Penalties and Slashing

There will be penalties for proposers and provers who do not fulfill their duties.

### Open Questions

- If proposers are selected randomly, do we need to enumerate all slashing conditions?
- If proposers are voted on, can we rely on the community to enforce penalties?
- What are the penalties for proposers and provers?
- How do we ensure that the penalties are fair?
- What should be burned, and what should be distributed?


