# Slashing conditions

We add two new slashing conditions related to building in chunks:

- A proposer that broadcasts via p2p two different block proposals for the same index within the same slot is slashed. This prevents the committee from attesting to two conflicting provisional chain heads. Note that this **breaks the high-availability setup** for proposers that run two simultaneous nodes. This should trigger a large slash.
- Equivalent slash but for an attestor who signed two different attestations for the same block.

Note that we do not to slash a sequencer if they fail to submit the L1 checkpoint altogether, since the sequencer may be honest but not be able to do so due to congestion.
