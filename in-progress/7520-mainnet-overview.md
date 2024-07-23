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

The objective of this document is to enable:
- engineering to define clear requirements and deliverables for TestNet
- external researchers to model the behavior of the system and optimize parameters
- the community to understand the design and provide feedback

This document **briefly outlines** key features of TestNet/MainNet. More detailed, technical designs on the individual components are forthcoming.

Some sections have open questions that need to be resolved before even the high-level design can be finalized.

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

Each deployment has:
- A Registry, which points to the contracts that make up the deployment. It also handles governance of the deployment.
- A Rollup Contract, which is the main contract that handles the rollup of transactions.
- A Data Availability Oracle, which is responsible for providing data published to our DA solution.
- An Inbox, responsible for receiving messages from L1 and making them available L2.
- An Outbox, responsible for receiving messages from L2 and making them available on L1.
- A Rewards contract, which handles the distribution of rewards to proposers, validators, and provers.

After the deployment is created, a proposal is submitted to the TLG, requesting funding of the Rewards contract.

There are two deployments as part of TestNet:
- Alpha: `testnet-alpha`
- Beta: `testnet-beta`

## Deployment Upgrades


<!-- An overview of the upgrade process for a deployment of the Aztec Network. This will include the mechanisms for proposing and implementing changes to the network, and how users interact with different versions of the network. -->

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

It will have two primary modes of operation:
- Proposer/Validator: responsible for proposing new blocks and validating them
- Prover: responsible for orchestrating the creation of various proofs

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

There will be a mechanism for selecting proposers and validators.

We are actively determining the best way to do this.

Key considerations include:
- Decentralization
- Security
- Economics

We will be working closely with the community and external researchers to design a system that is fair and secure.

### Open Questions

- How large should the validator set be?
- How many validators should be selected per epoch?

If we choose a system where a validator set is selected randomly and trustlessly based on staked AZT:
- How can we distribute rewards?
- How do we keep l1 costs low?
- How do we enumerate all possible slashing conditions?

If we choose a system where a validator set is voted on by AZT holders:
- Can this be sufficiently decentralized?
- How resistant is this to censorship?

In either scenario:
- How costly is it for users to participate?
- What are the economic incentives for validators?
- What is our security model?
- How much malicious AZT can we tolerate before we lose safety/liveness?

## Fees

Every transaction in the Aztec Network has a fee associated with it. The fee is payed in AZT which has been bridged to L2.

Transactions consume gas. There are two types of gas:
- L2 gas: the cost of computation on L2
- DA gas: the cost of data availability on L2

When a user specifies a transaction, they provide values:
- maxFeePerL2Gas: the maximum fee they are willing to pay in L2-AZT per unit L2 gas
- maxFeePerDAGas: the maximum fee they are willing to pay in L2-AZT per unit DA gas
- l2GasLimit: the maximum amount of L2 gas they are willing to consume
- daGasLimit: the maximum amount of DA gas they are willing to consume

Thus, the maximum fee they are willing to pay is:
- maxFee = maxFeePerL2Gas * l2GasLimit + maxFeePerDAGas * daGasLimit

There is an additional pair of parameters to support complex flow such as fee abstraction:
- l2TeardownGasLimit: the maximum amount of L2 gas they are willing to consume for the teardown of the transaction
- daTeardownGasLimit: the maximum amount of DA gas they are willing to consume for the teardown of the transaction

Both of these values are used to "pre-pay" for the public teardown phase of the transaction.

Each L2 block has a fixed L2 gas limit and a DA gas limit, each with a respective "target". 

Each L2 block dynamically sets its fee per L2/DA gas based on the deviation of the previous block's gas usage from the target.

### Open Questions

- Can we ensure that the cost of proving is covered by L2 gas?
- How do we pass back L1 compute and DA costs back to users?

## Enshrined Price Oracles

There will be an enshrined price oracle contract on L1 that protocol contracts will use to determine the exchange rate between AZT and Eth.

### Open Questions

- What guarantees can we provide about the price oracle?

## Pending Block Rewards

We do not plan to have rewards for pending blocks, as we only want to incentivize the finalization of blocks.

## Proven Block Rewards

We will have rewards for proven blocks.

These will largely be funded by the transaction fees.

### Open Questions

- How much do we need to subsidize proven blocks?
- How much should the protocol retain for future development?


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


## Censorship Resistance and Liveness

<!-- An overview of the censorship resistance and liveness model for the Aztec Network. This will include a description of the mechanisms for detecting and responding to censorship attacks. -->

## Safety

<!-- An overview of the safety guarantees for the Aztec Network in various scenarios. -->


## Performance

<!-- An overview of the expected performance of TestNet. This will include the throughput, latency, and scalability of the network. -->

