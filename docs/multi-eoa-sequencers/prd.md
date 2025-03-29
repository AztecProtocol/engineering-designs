# Multi-EOA Sequencers Project Requirements Document

- Owner: @just-mitch
- Approvers:
  - @LHerskind
  - @Maddiaa0
  - @spalladino
- Target PRD Approval Date: 2025-04-01
- Target Design Approval Date: 2025-05-09
- Target Delivery Date (master): 2025-Q3
- Target Delivery Date (production): 2025-Q3

Note: We can pull up delivery based on what we see/want in prod: if people are unable to vote while proposing then we need this sooner.

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

# Background

An Ethereum address can either choose to send legacy transactions **or** blob transactions at the same time to prevent some DDoS attacks. ([Ref](https://github.com/ethereum/go-ethereum/issues/28925#issuecomment-1925601084))

Further, because all transactions must respect the expected nonce value from the account, if a blob transaction is sent, but is not included within a desired timeframe, it must be cancelled or replaced; this operation is expensive, requiring [a 100% price increase from the initial (blob)gas prices](https://github.com/ethereum/go-ethereum/blob/6143c350ae1ecf3330678be02b4c2745bb6b8134/core/txpool/blobpool/config.go#L34).

Separately, sequencers in Aztec are able perform multiple actions during their slot, including:

- [propose](https://github.com/AztecProtocol/aztec-packages/blob/27f1eca25c4c5849d32541b5ad1d3068d5d1911a/l1-contracts/src/core/libraries/rollup/ProposeLib.sol#L71) a block to the L1 (a blob transaction)
- [signal/vote](https://github.com/AztecProtocol/aztec-packages/blob/27f1eca25c4c5849d32541b5ad1d3068d5d1911a/l1-contracts/src/governance/proposer/EmpireBase.sol#L55) at the governance proposer (non-blob)
- signal/vote at the slashing proposer (non-blob)

## Problematic scenarios

There are several circumstances then that can cause a sequencer to become effectively stalled.

### Archiver lag

Suppose a sequencer may propose a blob during L1 slots 3, 4, or 5. This means that the transactions from the sequencer may (should) arrive in L1 slot 2, to give the sequencer the greatest chance for their blob transaction to land within their 3 slot window. See [anatomy of a slot](https://www.blocknative.com/blog/anatomy-of-a-slot). However, the L2 block from the previous sequencer may be discovered somewhat late into slot 2. Thus the sequencer might have detected that their archiver is not in sync, and chose to submit a vote transaction. After the archiver comes in sync, the sequencer attempts to build a block, but must wait until slot 3 to submit the transaction (to be included in slot 4), which can significantly impair its chances of getting included. See [blob inclusion rates](https://ethresear.ch/t/slot-inclusion-rates-and-blob-market-combinatorics/19817): the data in that post is dated, but the broad concerns around having enough time for blob transactions remain.

### Gas price spike

If (blob)gas prices spike on ethereum, and the sequencer has not taken this into account, they might submit a transaction that sits in the mempool of their L1 client for several minutes, during which time they are unable to take any further action without cancelling/replacing the transaction.

## Definitions

- validator: the tuple of ethereum addresses (proposer, attester, withdrawer) which is staked into a particular aztec rollup instance on ethereum
- sequencer: the validator responsible for producing an aztec block during a specific period of time
- pending chain: what blocks proposed by sequencers are appended to

## Dependencies

The validators are able to separate their proposer from their attester. This proposer may be a deployed contract, e.g. a "MultiCall" or ["Forwarder"](https://github.com/AztecProtocol/aztec-packages/blob/27f1eca25c4c5849d32541b5ad1d3068d5d1911a/l1-contracts/src/periphery/Forwarder.sol#L9), which is then able to take multiple actions (and have multiple owners).

## Assumptions

- Validators may only vote at the governance proposer and slash proposer during their L2 slot for which they are sequencer.
- We use ethereum blobs for DA.

# User Stories

## End User

Alice is making transactions on Aztec. She is happy when they are promptly included in the pending chain.

## Sequencer

Sally Sequencer wants to make money running a validator on the aztec network.

Sally is happy when her node publishes Aztec blocks because that means she makes money when that block is proven.

Sally also participates in governance to make sure that measures which are beneficial to the network (and thus to her bottom line) are proposed and enacted, so she is also happy to see her node simultaneously building blocks and participating in governance.

That said, Sally doesn't want to be continually fiddling with her node to make sure she is producing blocks/votes.

# Requirements

## Functional Requirements

### FUNC01

The current sequencer **MUST** be able to propose a block and vote in the same L2 slot.

WHY: fallout from the system design assumption above.
WHERE: Sally Sequencer user story

## Non-functional Requirements

### ATTR01

Assuming their L2 block is valid, their L1 node is available, and they are willing to pay the applicable L1 fees, prior/concurrent interactions with the rollup **SHOULD NOT** cause any degradation in the percentage of L2 slots that a sequencer fills with blocks/votes.

WHY: missed slots degrades network performance both for end users (longer time to "Pending" confirmation) and node operators (lower revenue)
WHERE: end user and sequencer user stories.

### ATTR02

If needed, the current sequencer **SHOULD** prioritize their block submission over their voting.

WHY: it more important for network liveness, and blob transactions need more time to get included.
WHERE: end user story and developer apprehension

### ATTR03

Beyond updating payload addresses for votes, node operators **SHOULD NOT** need to make live updates to their node's configuration to ensure that they are consistently producing blocks.

WHY: if things are hard, people don't do them. in this case, that would mean degraded performance for all aztec users.
WHERE: sequencer user story.

### ATTR04

Node operators **MAY** need to perform periodic maintenance on their L1 accounts to ensure they are topped up on ether. This **MAY** require more than 1 L1 transaction, but the fewer the better.

WHY: same as ATTR03
WHERE: sequencer user story.

# Handling Tradeoffs

Solutions which make no changes to L1 contracts (other than the "Forwarder") are preferred.

Additionally, network liveness should be prioritized over node operator convenience.

Last, solutions ought to prefer stronger guarantees on sequencers' transactions being confirmed on L1 rather than minimizing costs.
