
# Template

|                      |                                            |
| -------------------- | ------------------------------------------ |
| Issue                | [title](github.com/link/to/issue)          |
| Owners               | @LHerskind @MirandaWood                    |
| Approvers            | @just-mitch @PhilWindle @iAmMichaelConnor  |
| Target Approval Date | YYYY-MM-DD                                 |


## Executive Summary

We will retire calldata for block bodies and instead use EIP-4844 blobs.

## Introduction

> Briefly describe the problem the work solves, and for whom. Include any relevant background information and the goals (and non-goals) of this implementation.

### Background

#### Our system 101
In our current system, we have an `AvailabilityOracle` contract.
This contract is relatively simple, given a bunch of transactions it will compute a commitment to them, by building a merkle tree from their transaction effects.
The root of this tree is then stored in the contract such that we can later check for availability.

When a block is proposed to the rollup contract, it will perform a query to the `AvailabilityOracle` to check availability of the `txs_effects_hash` of the header.

Since the only way it could be marked as available was by it being hashed at the oracle, we are sure that the data was published.

When the proof is to be verified, the `txs_effects_hash` is provided as a public input.
The circuits are proving that the "opening" of the commitment is indeed the transactions effects from the transactions of the block.

We are using just the hash for the public input instead of the transactions effects directly since it is a cost optimisation.
An extra public input have a higher cost than the extra layer of hashing that we need to do on both L1 and L2.
As the hashing are done both places, we use the `sha256` hash as it is relatively cheap on both sides.

It is a simple system, but using calldata and building the merkle tree on L1 is **very** gas intensive. 

#### What the hell is a blob?

- https://eips.ethereum.org/EIPS/eip-4844

Following 4844 (blob transactions), an Ethereum transaction can have up to 6 "sidecars" of 4096 field elements.
These sidecars are called blobs, and are by themselves NOT accessible from the EVM. 
However, a `VersionedHash` is exposed to the EVM, this is a hash of the version number and the kzg commitment to the sidecar.

```python
def kzg_to_versioned_hash(commitment: KZGCommitment) -> VersionedHash:
    return VERSIONED_HASH_VERSION_KZG + sha256(commitment)[1:]
```

If a `VersionedHash` is exposed to the EVM, the Ethereum network guarantees that the data (its 4096 fields) are published.

As you might have noticed, the `VersionedHash` and our `AvailabilityOracle` have a very similar purpose, if commitment is published according to it, then the pre-image of the commitment have also been published.

> Special Trivia for @iAmMichaelConnor:   
> The `to` field of a blob transactions cannot be `address(0)` so it cannot be a "create" transaction, meaning that your "fresh rollup contract every block" dream have a few extra hiccups. 
>Could still happen through a factory, but a factory make a single known contract the deployer and kinda destroy the idea.


### Goal 

Update the system to publish the transactions effects using blobs instead of calldata.

### Non-Goals

We do NOT change the data that is published, e.g., we will be publishing the transactions effects.

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
- [x] Private Kernel Circuits
- [x] Sequencer
- [ ] AVM
- [x] Public Kernel Circuits
- [x] Rollup Circuits
- [x] L1 Contracts
- [x] Archiver
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.


### Solidity

Forge does allow emitting a blob, however, it allows for mocking a set of KZG hashes, 

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
