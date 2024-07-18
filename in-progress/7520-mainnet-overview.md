# MainNet Overview

|                      |                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------- |
| Issue                | [MainNet Design Overview](https://github.com/AztecProtocol/aztec-packages/issues/7520) |
| Owners               |                                                                                        |
| Approvers            |                                                                                        |
| Target Approval Date | 2024-08-06                                                                             |


## Executive Summary

This document is a system design overview of what we want to deliver as our MainNet release.

We want to deliver a fully functional network by the end of 2024. This network will be a publicly available, but with no guarantees of security or stability.

The deployed network will be referred to as "TestNet", but it should reflect the design of the MainNet in areas including:
- Proof of stake
- Fees and rewards
- Slashing conditions
- Upgrades
- What we publish to DA
- How we are using blobs
- Prover marketplaces

Thus, in the immediate term, Aztec Labs will be running two networks:

- DevNet: a public network with a centralized sequencer and prover
- SPRTN: a public network with permissioned sequencers and provers

These will be consolidated into:
- TestNet: a public network with decentralized sequencers and provers

This document needs to be detailed enough for blockscience to be able to start modelling economics of the system (to establish the best parameters that work), and for publishing on our forums for public scrutiny and feedback.

## Introduction

Briefly describe the problem the work solves, and for whom. Include any relevant background information and the goals (and non-goals) of this implementation.

## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] Aztec.nr
- [ ] Noir
- [ ] AVM
- [ ] Sequencer
- [ ] Fees
- [ ] P2P Network
- [ ] Cryptography
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
