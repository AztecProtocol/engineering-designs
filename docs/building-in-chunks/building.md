# Intro

Design for block-building under building in chunks.

# Block building

Proposers now partition their slot time into chunks. The duration of is chunk is configurable and defaults to 12s initially. During the first chunk, they accumulate txs into a block until they hit a time, gas, or tx count limit. They then close that block, sign over it, and broadcast the block proposal across the p2p network. They also commit the block to their own archiver as **proposed**.

As soon as the second chunk of time begins, the proposer starts production of the second block. Validators in the committee receive this proposal and start reexecution. As soon as reexecution is complete, they commit that block to their archiver as **proposed**.

On the last block within their slot, the proposer broadcasts a full **checkpoint** instead. Validators execute the txs from this last block and sign over the checkpoint, and broadcast back their attestation. The proposer collects them and uses them for posting to L1.

The proposer allocates a configurable number of seconds (defaults to 24s) for getting the checkpoint mined on L1. The last block within the checkpoint should end earlier if necessary to allow for this time.

## Attestations

When an attestor for a slot receives a block proposal for a fresh slot, it validates the new block header, and starts reexecution using a world state fork. If reexecution and validation pass, it commits the new block to the archiver as proposed. As an optimization, it may also commit its world-state fork to avoid having to reprocess the block once committed to the archiver.

Note that an attestor must hold off reexecuting a block proposal until it has reexecuted all previous proposals in the given slot. If a proposal for block N+1 within a slot arrives while the attestor unattested chain is not yet at block N, it should wait and not reject the proposal.

## Proposed blocks

A proposed block is equivalent to the data posted to L1. It contains a checkpoint header, block header, committee attestations, and the proposer signature over all data. Note that this proposer signature guarantees that it is the proposer who decides when a block within a slot is added to the proposed chain. Nodes verify this signature before accepting and reexecuting a new proposed block.

Note that proposed blocks are **not** attested to (only the last one within a slot is). Any node that wants to follow the **proposed** chain needs to reexecute every tx, regardless of them being a validator or not.

## Staggered slots

In our current design, a proposer does not start building for their slot until they have synced the previous one from L1. This means that part of the slot time needs to be allocated to getting the L1 checkpointing tx mined, which reduces how much time is available for actual block building.

Instead, as an optimization, we can build the blocks for slot N during slot N-1, and we use slot N exclusively for publishing to L1, while the next proposer builds the blocks for slot N+1. This means we get much more time for publishing, which we'll need if we require more than one blob per checkpoint, and we are continuously building blocks, which enables higher TPS.

Note that, in the unhappy path in which a proposer fails to publish their L1 checkpoint, the block built by the following proposer is invalidated, so the provisional chain is reorged back by two slots. It could be possible for any node in the network to pick up the blocks produced for a given slot and upload to L1 (see "better economic guarantees" in the [original design](../../attic/building-in-chunks/dd.md#better-economic-guarantees)), but building that machinery is out of scope for the moment.
