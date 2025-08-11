# Multi-EOA Design Document

- Owner: @spalladino
- Approvers: @PhilWindle

## Summary

As described on the product requirements document, we want to ensure that prior txs sent to L1 do not negatively impact any subsequent txs sent. We propose doing so by having multiple externally-owned accounts that act as publishers (aka relayers) by sending txs, so we can rotate them if needed.

See also the [`keys-config`](../keys-config/prd.md) document on how keys are configured.

## Context

Aside from bootstrapping (such as deploying L1 contracts), the Aztec node sends txs to L1 for the following purposes:

- As a **sequencer**, it sends blob txs proposing new L2 blocks. These txs may be part of a [multicall](https://www.multicall3.com/) where the proposer also votes for a proposal, or invalidates a block. In rare circumstances, the sequencer will send a multicall with only a vote or an invalidation, but without a block (and hence without blobs). Block proposals and votes have a specific set of L1 blocks in which they may land, after those they "expire", meaning they'd revert when mined. Block proposal txs carry 1-6 blobs and cost 100k-400k gas, while votes and invalidations cost about 200k-800k gas. These txs are sent at most once per checkpoint, which is 3-12 L1 slots.
- As a **prover**, it sends a tx with a validity proof for an epoch. These txs also have an expiration window, after which they revert if they'd land. No blobs are used. The cost is 1M-4M gas, and these txs are sent at most once per epoch, which is about 96-384 L1 slots.

A distinct property of all these txs is that they are **non-sequential**, meaning we do not care for Ethereum's increasing nonces for ordering.

## Algorithm

We keep all our _publishers_ split by "scope", where the scope may be _proving_ or _sequencing_. If sequencing, publishers are also scoped by validator address, so a node that runs multiple validators may use different publisher accounts for each validator, to avoid publicly linking them. Note that a publisher may belong to more than one scope.

Each publisher account is in one of the following states:

- `idle`
- `tx-sent`: A tx has been sent and is awaiting for it to be mined
- `tx-speed-up`: The original tx has been replaced with the same tx but higher gas price
- `tx-cancelled`: The tx has expired, so it has been replaced with a noop tx
- `tx-not-mined`: The tx and its replacements have expired without being mined, and we have given up on it
- `tx-mined`: The tx or one of its replacements (ie a tx with the same nonce) has been mined

The final state `tx-mined` transitions back to `idle` after a configurable amount of time, to account for L1 reorgs. As for `tx-not-mined`, we only transition once the tx is no longer found in the mempool for a configurable amount of time.

When sending a tx for a given scope, we choose from all publishers for the scope in the following order:

- `idle`: The publisher is ready to be used
- `tx-mined`: The publisher is ready to be used (assuming no L1 reorgs)
- `tx-cancelled`: We try [replacing the cancelled tx with the new one](https://github.com/AztecProtocol/aztec-packages/pull/15713)
- `tx-not-mined`: We try reusing the nonce from the not-mined tx to replace it, though this is risky as the not-mined tx may actually be mined before we broadcast the new tx.

If there is more than one publisher in the same state to choose from, we prefer choosing the least recently used one, though ordering by balance (highest balance first) is also acceptable.

Note that business logic dictates we should never try sending a tx while the previous one is in flight and not expired. If we try doing so, and all available publishers are in state `tx-sent` or `tx-speed-up`, then throw an exception.

Also, available publishers should be filtered by balance, ensuring that the given EOA has enough funds to send the tx, and possibly replace it with a larger gas price. If we detect a publisher account has not enough gas, we should warn (bonus points if we warn before running out).

### Funder accounts

As an optional feature, we can define a key as **funder**, with the sole purpose of topping up the other accounts when they run low on funds. Funder accounts should not be used for sequencing or proving. Funder accounts may be defined globally or scoped per validator. Defining a funder account globally makes it easier to manage, but leaks privacy by linking the validator accounts together.

## Architecture

Publishers should be managed by a new "service", similar to the EpochCache, that should be a dependency of the sequencer publisher and prover publisher. We can have a single service that handles _all_ keys, and then each component asks for the keys for its scope, or we could have a different instance of this service for each scope (sequencer, prover). I slightly prefer the latter.

This service could live in a new package, in the `ethereum` package, or in `stdlib`. Note that this service will likely use most methods from `l1-tx-utils`, which is the library being used by the sequencer publisher and prover publisher for sending L1 txs.

The service should hydrate the state for all publishers when starting, in case it is restarted with a tx in-flight. At a minimum, it should detect if there are pending txs by checking account nonces. If needed, it could use a store to keep more detailed state for each publisher account.

## Testing

In addition to the expected set of unit tests, we should set up an end-to-end test that covers the main use case for this feature: an unmined L2 block proposal does not block sending a later one if the same node is picked as validator for two contiguous blocks. Note that it may be necessary to manually drop an L1 tx from anvil using cheatcodes, and mock the RPC so that the node thinks the tx is still in the mempool.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
