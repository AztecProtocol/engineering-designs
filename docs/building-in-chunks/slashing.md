# Slashing conditions

We add two new slashing conditions related to building in chunks:

- A proposer that broadcasts via p2p two different block proposals for the same index within the same slot is slashed. This prevents the committee from attesting to two conflicting provisional chain heads. Note that this **breaks the high-availability setup** for proposers that run two simultaneous nodes. This should trigger a large slash.
- A proposer that uploads to L1 a subset of the provisional chain is slashed. This prevents proposers from having the free option to remove part of the provisional chain at their discretion. This should trigger a large slash. In other words, omitting the final provisional block from an L1 checkpoint is a slashable offense. Note that a block is considered provisional only once the sequencer has broadcasted a "provisional block finalized" message which includes its attestations.

Note that we do not to slash a sequencer if they fail to submit the L1 checkpoint altogether, since the sequencer may be honest but not be able to do so due to congestion.
