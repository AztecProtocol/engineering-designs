# Intro

Overview and index for the design for building in chunks.

## Overview

Building-in-chunks refers to building multiple L2 blocks per L1 checkpoint. We define an L1 checkpoint as every time we commit the state of the chain to the L1 rollup contract. Each L1 checkpoint maps to an L2 slot, so each L2 slot may now contain multiple L2 blocks. During an L2 slot, the proposer and committee are fixed.

## Goals

- **Usability**: Improved latency for users by adding a new finalization stage before L1-mined. This also allows users to use the effects of a tx in a subsequent one sooner, by making the resulting state tree root available sooner.
- **Cost**: Reduced gas cost by amortizing the fixed L1 proposal cost across more blocks.

## Target

Achieve ~36s block times with 72s L2 slot times.

## Resources

- [Original design document](../../attic/building-in-chunks/dd.md) with motivations
- [Building](./building.md) on how sequencers and validators assemble multiple blocks per slot
- [Syncing](./syncing.md) on how nodes in the network access the blocks
- [Messages](./messages.md) updated p2p message types related to building in chunks
- [Circuits](./circuits.md) spec on changes to circuits
- [Slashing](./slashing.md) new slashing conditions
- [Contracts](../../attic/building-in-chunks/batch-propose.md) on changes to rollup contract and gas savings (outdated)
