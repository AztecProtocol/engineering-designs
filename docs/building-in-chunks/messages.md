# Peer-to-peer messages

Overview of updated peer-to-peer messages related to block building and syncing for building in chunks.

## Block proposals

The former L2 block header is now split into checkpoint header and block header. The proposer will broadcast the checkpoint header and block header for the first block proposal within a checkpoint, and then just the block header for all subsequent block proposals to attestors. Note that certain fields of the checkpoint header, such as the content commitment, are only known once the entire checkpoint is closed, so the proposal will not include these values.

As an alternative, for simplification, we may decide to include the checkpoint header in every block proposal, at the expense of slightly bigger proposals on the p2p network.

## Attestations

Attestations are modified to reference a hash of the new block proposal, so they include checkpoint data as well.

Note that attestations today include the entire `ConsensusPayload`, which is all data from the proposal. We can drop this in favor of including just a hash of the proposal, plus any data using for identifying the proposal, such as archive root, block number, and slot number. This would greatly reduce data transmitted over p2p for attestations.

## Provisional blocks

Once a block has been attested, the proposer broadcasts a message that includes the checkpoint header, block header, and all required attestations for it. The proposer must sign over all these fields. Nodes rely on this message for syncing the provisional chain.

Note that this signature must NOT be the same signature as the one expected by the rollup contract, otherwise any node could upload a provisional block to the rollup contract before all blocks for the slot had been produced.
