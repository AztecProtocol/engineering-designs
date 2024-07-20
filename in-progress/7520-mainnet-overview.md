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

<!-- An overview of the governance model for the Aztec Network. This will include the roles of the various stakeholders, the decision-making process, and the mechanisms for proposing and voting on changes to the network. -->

There is a Top Level Governance (TLG) contract, and an Aztec Token (AZT) contract deployed on L1. 

Neither contract is tied to any specific deployment of the Aztec Network.

The TLG is a minter of the Aztec Token.

Holders of AZT will be able to submit proposals to the TLG, which will be voted on by AZT holders.

## Network Deployments

<!-- An overview of how different components of the Aztec Network are deployed on Ethereum L1, and how they interact with Top Level Governance. -->

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

## Compliance

<!-- An overview of the compliance model for the Aztec Network. This will include the mechanisms for enforcing compliance with regulations, the tools for monitoring and reporting on transactions. -->

## Bridging and Messaging

<!-- An overview of the bridging model for the Aztec Network. Describes how assets and messages are passed between L1 and L2. -->

## Enshrined L2 Contracts

<!-- An overview of the enshrined L2 contracts for the Aztec Network. This will include the roles of the various contracts, and the mechanisms for interacting with them. -->

## Contract Interaction

<!-- An overview of how users deploy and interact with contracts on the Aztec Network. -->

## Aztec Labs Node

Aztec Labs will provide a reference implementation of the Aztec Node, which will be used to run the Aztec Network.

It will have two primary modes of operation:
- Proposer/Validator: responsible for proposing new blocks and validating them
- Prover: responsible for orchestrating the creation of various proofs

The node will have a web interface for monitoring key metrics.

## Chains

<!-- An overview of the chains that make up the Aztec Network. This will include the roles of the various chains, a description of slots/epochs, how blocks are produced, validated, and moved between chains.  -->

There are two chains in the Aztec Network:
- The Pending Chain
- The Proven Chain
- The Finalized Chain

All three chains are effectively managed by the Aztec Node and the L1 contracts, and have different guarantees.

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

## The Pending Chain

The purpose of the pending chain is to reduce the perceived latency of transactions: it allows clients to observe transactions that have been proposed, but the proof has not yet been made available.

The proposer for a slot produces a list of transaction objects either by
- selecting them from the L2 mempool,
- or receiving a list from a builder.

The proposer gossips to the validators:
- A signature showing it is the current proposer
- The list of transaction objects

Validators check that the proposer is the current proposer, and that the transactions are valid.

If the transactions are valid, the validator computes a hash of the list of transaction objects and signs it, and gossips the signature.

Note, the validators do not need to execute the transactions.

The proposer collects the signatures from the validators, and once it receives M/N signatures, it publishes the list of transaction objects and the signatures to DA.

Additionally, it submits a transaction to the Rollup contract which...

Nodes serving the pending chain:
- download the list of transaction objects and signatures
- check the signatures
- check the transactions are valid
- execute the transactions and apply the resulting state diffs to their local state

## The Proven Chain

## The Finalized Chain



## Proposers

<!-- An overview of the role proposers play in the Aztec Network, as well as their high-level architecture. Includes a description of the tools for monitoring sequencer performance. -->

## Validators

<!-- An overview of the role sequencer/proposers play in the Aztec Network, as well as their high-level architecture. Includes a description of the tools for monitoring sequencer performance. -->

## Provers

<!-- An overview of the role prover plays in the Aztec Network, as well as their high-level architecture. Includes a description of the tools for monitoring prover performance. -->

## Proposer/Validator Selection

<!-- An overview of how proposers/validators are selected in the Aztec Network. -->

## Prover Selection

<!-- An overview of how provers are selected in the Aztec Network, touching on the prover marketplace. -->



## Prover Coordination

<!-- An overview of how proposers and provers coordinate in the Aztec Network. -->



## Transaction Lifecycle

<!-- An overview of the lifecycle of a transaction in the Aztec Network. This will include the steps involved in creating, submitting, validating, and finalizing a transaction, as well as the mechanisms for monitoring and reporting on the status of a transaction. -->

## Fees

<!-- An overview of the fee model for the Aztec Network. This will include the mechanisms for calculating and collecting fees. -->

## Incentives

<!-- An overview of the incentive model for the Aztec Network. This will include the mechanisms for rewarding proposers, validators, and provers. -->

## Data Availability

<!-- An overview of the data availability model for the Aztec Network. This will include a description of what data is published where, how, and by whom. -->

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
