# Intro

Design document for a variant of building in chunks with chained transaction support where we submit L2 blocks to L1 in batches. This is based on [this suggestion](https://github.com/AztecProtocol/engineering-designs/pull/70#pullrequestreview-3019840618) from @LHerskind.

## Overview

We define an L1 **checkpoint** ("frame" in the original proposal) as a new period of time, composed by multiple slots. Within a checkpoint, the proposer is always the same. The `Rollup.propose` function now accepts multiple L2 blocks instead of one, up to one for each slot. Only the attestations for the last block in the checkpoint are posted and validated, since any invalid block within the checkpoint would invalidate all subsequent blocks. The batch requires a mapping from blob index to block within the batch.

This requires no circuit changes, and requires changes in the node related to building in chunks.

## Numbers

### Checkpoint and slot durations

Since we are not making changes to circuits, each block still takes up at least one blob. If we target 6 blobs per tx, which may reduce our chances at L1 inclusion, we can squeeze no more than 6 slots per checkpoint. Assuming 1200 bytes per tx effect, each 128kb blob can carry about 100 txs. Assuming 10 TPS, we require 12kb per second for DA, which is 1 blob every 10.6 seconds, roughly 1 blob per L1 slot. This means the duration of a checkpoint cannot be more than 6 L1 slots (72s), and the duration of each L2 slot should be equivalent to one L1 slot (12s).

Note that the above assumes 10TPS. If we go below this, then each block would not fully utilize its blob, leading to wasted blobspace and increased DA cost per tx. We should expect proposers to **not** produce a block for a slot if they have not filled the block, and instead accumulate txs into the following block in the slot within their checkpoint. This leads to less DA cost, which is borne by the proposer, but worse UX, since users now have to wait longer for L2 inclusion.

If we land at lower TPS or less bytes per tx, this can lead to worse UX overall, since a proposer would be incentivized to only post a single block within their checkpoint, effectively increasing block times to 72s. If we assume 300 bytes per tx, which is the current lower bound for a transfer with out-of-band messaging (which should be the preference for app developers who want to reduce tx costs) at 6 TPS, a single blob takes the full 72s to be filled.

On the other hand, if we consider 2400 bytes per tx effect, which is the size of a transfer with fpc support with all notes posted on-chain, then each blob can carry about 50 txs only. Assuming 10 TPS, this means we fill 2 blobs per L1 slot, so checkpoints cannot be longer than 3 L1 slots (36s).

**TLDR**:

- At 10 TPS with 1200 byte txs, checkpoints happen every 72s, block time is 12s (good)
- At 6 TPS with 300 byte txs, block time is 72s (bad UX)
- At 10 TPS with 2400 byte txs, checkpoints happen every 36s, block time is 6s (worst cost)

### Gas savings

Following are the actions we do in `Rollup.propose` as of today, and whether they can be done once per batch or would still have to be repeated once per block. Gas costs are estimated from [this doc](https://hackmd.io/j-H-8k8dRYSAjXCpzk4WPg).

| Action                         | Per block | Per batch | Gas cost |
| ------------------------------ | --------- | --------- | -------- |
| Base tx cost                   |           | x         | 21k      |
| Post blob inputs               | x         |           | 20k      |
| Setup epoch                    |           | x         | 3k       |
| Update L1 gas fee oracle       |           | x         | 8k       |
| Validate blob commitments      | x         |           | 8k       |
| Compute base fee               |           | x         | 22k      |
| Validate block header          | x         |           | 20k      |
| Post and validate attestations |           | x         | 200k     |
| Update pending chain tip       |           | x         | 3k       |
| Store archive root             | x         |           | 22k      |
| Store block log                | x         |           | 30k      |
| Consume inbox                  | x         |           | 10k      |
| Push messages to outbox        | x         |           | 9k       |
| Emit log                       | x         |           | 3k       |
| Unaccounted for                |           | x         | 20k      |

The total gas cost from `propose` today is then 400k gas every 36s, or 11k gas per second. Under this new model, the cost per block is `20 + 8 + 20 + 22 + 30 + 10 + 9 + 3` or 122k gas, and the cost per batch is `21 + 3 + 8 + 22 + 200 + 3 + 20` or 277k gas. Assuming 72s checkpoints:

- With 72s checkpoints and 12s blocks (best for UX), total gas cost per checkpoint is 1M, or 14k gas per second (worse than status quo)
- Decreasing block frequency to once per 36s (same UX as today), total gas cost per checkpoint is 521k gas, or 7k gas per second (33% better than status quo)
- Halving checkpoints to 36s to support 2400-byte txs, with one block every 6s (best for UX), total gas cost is 1M, or 28k gas per second (much worse than status quo)

## Changes required

Total 8 weeks of effort.

### L1

- Change proposer selection such that it is stable throughout a checkpoint
- Update `propose` to accept a batch of blocks and a blobindex-to-block mapping

### Node

- Implementing one of the base versions of building in chunks from the main design document (5 weeks)
- Update the sequencer publisher to batch multiple blocks together.

## Security implications

A longer monopoly time by a single proposer means higher chance of price manipulations by that proposer, longer inactivity periods if the proposer is offline, and longer censorship periods when a malicious proposer is chosen.
