# [MainNet Design Overview](https://github.com/AztecProtocol/aztec-packages/issues/7520)

|                      |            |
| -------------------- | ---------- |
| Owners               |            |
| Approvers            |            |
| Target Approval Date | 2024-08-06 |


This document is a system design overview of what we want to deliver as our MainNet release.

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

<!-- An overview of the Aztec Token (AZT). This will include the tokenomics of AZT, the mechanisms for staking and voting with AZT, utility, bridging, and restrictions on AZT. -->

## Compliance

<!-- An overview of the compliance model for the Aztec Network. This will include the mechanisms for enforcing compliance with regulations, the tools for monitoring and reporting on transactions. -->

## Bridging and Messaging


<!-- An overview of the bridging model for the Aztec Network. Describes how assets and messages are passed between L1 and L2. -->

## Enshrined L2 Contracts


<!-- An overview of the enshrined L2 contracts for the Aztec Network. This will include the roles of the various contracts, and the mechanisms for interacting with them. -->

## Contract Classes and Instances

<!-- An overview of the contract classes and instances in the Aztec Network. This will include the mechanisms for deploying and interacting with contracts. -->


## Contract Interaction

<!-- An overview of how users deploy and interact with contracts on the Aztec Network. -->

## Aztec Labs Node

Aztec Labs will provide a reference implementation of the Aztec Node, which will be used to run the Aztec Network.

It will have two primary modes of operation:
- Proposer/Validator: responsible for proposing new blocks and validating them
- Prover: responsible for orchestrating the creation of various proofs

The node will have a web interface for monitoring key metrics.


## Private Execution Environment (PXE)

Users interact with the Aztec Network via a trusted, Private Execution Environment (PXE), which can be run in a laptop browser.

This is a "trusted" environment in the sense that the PXE can see the user's private inputs to transactions, and manages keys.

When a user interacts with the network they submit a "Transaction Execution Request" to the PXE.

The PXE executes the private portion of the transaction locally, and generates a proof of correct execution.

The PXE submits to the network:
- A proof of correct private execution (the "private proof")
- The "transaction object"
  - The resulting "state diff" after private execution (transaction ID, new note hashes, nullifiers, etc.)
  - Execution logs
  - Enqueued public function calls (if any)

## Chains

There are two chains in the Aztec Network:
- The Pending Chain
- The Proven Chain
- The Finalized Chain

All three chains are effectively managed by the Aztec Node and the L1 contracts, and have different guarantees.

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

They first submit the TxObjects to DA, and then the block header calldata to a function on the rollup contract dedicated to advancing the pending chain.

## The Proven Chain

The purpose of the proven chain is to verify the correctness of the transactions in the pending chain.

It is a prefix of the pending chain.

The first block in an epoch must contain a commitment on behalf of the proposer to proving the current epoch.

This is done by placing a large "prover commitment bond" in the block.

The proof of epoch `i` must be submitted within a certain number of L1 blocks after the end of epoch `i`.

If this does not happen, there is an "open challenge period" where anyone can submit a proof of the epoch, and claim part of the prover commitment bond.

If no proof is submitted, the proposer loses the bond, and the epoch is considered invalid.

The proposer who posts the prover commitment bond must to coordinate payment and proving out of protocol.

Some users may coordinate with prover marketplaces, but the Aztec Node will come with the ability to "self-prove" an epoch.

## The Finalized Chain

The purpose of the finalized chain is to provide a final, immutable (up to Casper FFG) record of the state of the Aztec Network.

It is a prefix of the proven chain, and blocks naturally move from the proven chain to the finalized chain as proofs become finalized in the eyes of L1.

## Proposers

<!-- An overview of the role proposers play in the Aztec Network, as well as their high-level architecture. Includes a description of the tools for monitoring sequencer performance. -->

## Validators


<!-- An overview of the role sequencer/proposers play in the Aztec Network, as well as their high-level architecture. Includes a description of the tools for monitoring sequencer performance. -->


## Proposer/Validator Selection


<!-- An overview of how proposers/validators are selected in the Aztec Network. -->

## Fees

<!-- An overview of the fee model for the Aztec Network. This will include the mechanisms for calculating and collecting fees. -->

Every transaction in the Aztec Network has a fee associated with it. The fee is payed in AZT which has been bridged to L2, i.e. "L2-AZT".

Transactions consume gas. There are two types of gas:
- L2 gas: the cost of computation
- DA gas: the cost of data availability

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

The fees of all transactions are summed, and paid out to the L1 Rewards contract, which in turn distributes them to the proposer and validators of the block.

## Enshrined Price Oracles

There will be an enshrined price oracle contract on L1 that protocol contracts will use to determine the exchange rate between AZT and Eth.

## Pending Block Rewards

When a block is added to the pending chain, rewards in AZT are paid out from the Rewards Contract to proposers and validators who participated in the block.

## Proven Block Rewards



## Transaction Lifecycle

<!-- An overview of the lifecycle of a transaction in the Aztec Network. This will include the steps involved in creating, submitting, validating, and finalizing a transaction, as well as the mechanisms for monitoring and reporting on the status of a transaction. -->

## Data Availability

We will use ethereum blobs to publish TxObjects and proofs.


## Penalties and Slashing

<!-- An overview of the penalty and slashing model for the Aztec Network. This will include a description of various attacks on the network, and the mechanisms for penalizing proposers, validators, and provers. -->

## Censorship Resistance and Liveness

<!-- An overview of the censorship resistance and liveness model for the Aztec Network. This will include a description of the mechanisms for detecting and responding to censorship attacks. -->

## Safety

<!-- An overview of the safety guarantees for the Aztec Network in various scenarios. -->

## Private State

<!-- An overview of the private state model for the Aztec Network. This will include a description of how private data is stored, accessed, and updated. -->

## Public State

<!-- An overview of the public state model for the Aztec Network. This will include a description of how public data is stored, accessed, and updated. -->

## AVM

<!-- An overview of the Aztec Virtual Machine (AVM). This will include a description of the architecture, the instruction set, and the tools for monitoring and reporting on the performance of the AVM. -->

<!-- Include a description of the proving system used in the AVM. -->

## Client Proving System

<!-- An overview of the client proving system for the Aztec Network, touching on UltraHonk, Protogalaxy, and Goblin and providing rough hardware requirements for running the client proving system. -->

## Public Kernel Proving System

<!-- An overview of how public kernel circuits are proven. -->

## Rollup Proving System

<!-- An overview of how rollup circuits are proven. -->

## Performance

<!-- An overview of the expected performance of TestNet. This will include the throughput, latency, and scalability of the network. -->

