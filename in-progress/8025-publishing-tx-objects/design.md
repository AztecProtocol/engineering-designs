# Publishing TxObjects

|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [title](github.com/link/to/issue) |
| Owners               | @just-mitch @LHerskind @Maddiaa0  |
| Approvers            |                                   |
| Target Approval Date | 2024-09-11                        |


## Executive Summary

We currently publish transaction effects to L1. This means we execute the public portion of the transaction, accumulate all of its side effects, and publish those to the L1 contract. 

In contrast, we're moving to a world where we simply publish the outputs of the private execution (performed by a user's PXE) and the public call requests. 

Further, we are not requiring validators participating in the pending chain to execute transactions, and are merely required to verify the private proofs of transactions in a block that has been proposed.

## Introduction

We first outline the changes needed in various components to support this work.

### What is published, when

A proposer will collect signatures from the committee, and then publish (within a single  L1 transaction) the data to DA oracle contract, and a proposal to the rollup contract.

To the DA oracle contract, the proposer will publish the following data:
- Blobs
  - Tx1
    - max fee
    - note hashes (from private)
    - nullifiers (from private)
    - l2ToL1Messages (from private)
    - note encrypted logs (from private)
    - encrypted logs (from private)
    - unencrypted logs (from private)
    - public call request 1
      - contract address
      - call context
        - msgSender
        - storageContractAddress
        - functionSelector
        - isDelegateCall
        - isStaticCall
      - args
    - public call request 2
    - ...
  - Tx2
  - ...


To the rollup contract, the proposer will publish:

- CallData
  - numTxs
  - txsHash (a commitment to first nullifiers of all transactions in the (eventual) block)
  - inHash
  - GlobalVariables
    - slotNumber
    - timestamp
    - coinbase
    - feeRecipient

#### DA Oracle Changes

Keeps track of the versioned KZG hashes that were present in a transaction.

#### Rollup Contract Changes

### Forced inclusion of transactions

### Blob circuits

### Rollup circuits

### Prover interactions

### Keeping track of chain state

How do nodes keep track of the pending archive since they are not published to L1?

### Private kernel verification

Validators need to verify the private kernels

### Transaction invalidation

The rollup should *only* fail if the private kernel is invalid.

Presently the rollup will fail if any of the following conditions happen:
- Make list



## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.

## Documentation Plan

Identify changes or additions to the user documentation or protocol spec.


## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
