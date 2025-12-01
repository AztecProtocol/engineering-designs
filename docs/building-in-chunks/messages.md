# Peer-to-peer messages

Overview of updated peer-to-peer messages related to block building and syncing for building in chunks.

## Block and checkpoint proposals

The former L2 block header is now split into checkpoint header and block header. The proposer will broadcast the block header for the first block proposals within a checkpoint, and for the last block within the slot it will broadcast the full checkpoint header, which validators will need to sign on.

Both include a list of txs to be included in the block. The checkpoint proposal should be understood as a "last block within the slot" proposal.

## Attestations

Attestations are done over checkpoint proposals, similar as they are today.
