# Locked Inflation PRD

Owner:

- @amin3x

Approvers:

- @jaosef
- @LHerskind
- @AndreOxski

Target Approval Date: 2025/03/18
Target Project Delivery Date: 2025/04/15

## Key Words

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC [2119](https://datatracker.ietf.org/doc/html/rfc2119).

## Background

All block inflation must be locked until a global liquidity event.

## Desired User Flows

Sequencers and Provers MUST accrue block inflation as usual. They MUST NOT be able to claim them until governance has made it possible to do so.

Caveat: We accept the possibility that Governance can unlock block inflation anytime before such a liquidity event - that is fine.

Throughout the locked period, some provers MAY receive gas refunds spent on verifying epoch proofs. This is okay to be a manual process.

## User Stories

### Sequencer

As a sequencer, I should continue to accrue block inflation as I propose new blocks to the chain. I should always know how much block inflation I've accrued in order to determine my efficiency at recouping costs of providing services to the network.

### Provers

As a prover, I should continue to accrue block inflation as I submit new proofs that are verified by the rollup smart contract. I should always know how much block inflation I've accrued in order to determine my efficiency at recouping costs of providing services to the network.

### Governance

As the Aztec Governance, I should be able to start and pass a proposal to:

1. unlock all previously accrued block inflation,
2. allow owners to claim them,
3. remove the lock on future block inflation

## Requirements

1. All block rewards MUST be locked, for provers and sequencers.
2. Block rewards MUST only be unlocked at the earlier of:
   - A preset date: 1 month before any ATPs are unlocked.
   - A governance proposal is passed that unlocks all rewards.
3. Sequencers and provers MUST be able to query their accrued reward balances at any time.
4. Governance MUST have the ability to trigger the unlock of any previously locked block inflation.

| Requirement   | Why does it exist?                                                                                                                           |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Requirement 1 | Distribution happens after Ignition. Unlocked block rewards will create unforeseen challenges that we don't want to deal with.               |
| Requirement 2 | ATPs MUST NOT unlock a single token before the bootstrapped ignition set is fully unlocked including block inflation earned during Ignition. |
| Requirement 3 | Seems harmless.                                                                                                                              |
| Requirement 4 | To make sure block inflation isn't locked forever.                                                                                           |
