# Fast-Sync Project Requirements Document

- Owners: @spalladino, @aminsammara
- Approvers:
  - @andre
  - @charlielye
  - @PhilWindle
  - @joshcrites

## Background

Syncing an L2 node requires crawling L1 since L2 genesis, downloading events and blobs, and updating world-state for every update. This is time-consuming, and proportional to the length of the chain.

## Desired User Flow

Node operators should be able to sync the chain in nearly constant time by downloading a recent snapshot, and syncing only the most recent blocks. Operators should be able to do this by specifying a snapshot URL to sync from.

This flow is available in most Ethereum clients.

### Node operators

Users SHOULD be able to specify which method to use to sync their clients. Methods are either `fast` (snapshots) or `full` (for syncing from the chain). Default is `fast`. For example:
`aztec start --node --publisher --sync-method fast`

Users SHOULD also be able to specify the location for the snapshot. Protocols supported are ipfs and https. For example:
`aztec start --node --publisher --sync-method fast --snapshot-url ipfs://...`

Users SHOULD also be able to specify the location for a snapshot index, which is a machine-readable file that lists the latest snapshots. Protocols supported https only. For example:
`aztec start --node --publisher --sync-method fast --snapshot-index https://...`

### Labs

Snapshots for external networks must be generated and uploaded by Labs to IPFS on at most a 2-week basis, ideally weekly. This process should be automated.

## Requirements

- Snapshots can be client-specific.
- Snapshots are not to downloaded via p2p.
- Any regular node should be able to generate the snapshot with a given command.
- Nodes must be able to specify which snapshot to sync from by supplying an IPFS CID or URL.
- The IPFS gateway used by the node is configurable, and has a reasonable default (eg node run by Labs or well-known service).
- Nodes must also be able to specify a snapshot index, and pick the latest one listed.
- The time for syncing from a snapshot (without validating it) should not depend on the chain length (other than I/O).

### Snapshots index

The format of the snapshots index is left open, but must include the L2 block hash and number, corresponding L1 block number, and either an https or ipfs identifier for obtaining the corresponding snapshot data. This file must be machine-readable, ideally JSON.

### Trust assumptions

For an initial version of this feature, snapshots are trusted, meaning that the downloader trusts the uploader and does not verify its integrity. It only checks that the resulting world state root and latest archive match valid on-chain values.

### Hosting and defaults

Aztec Labs is to generate these snapshots on a weekly basis (preferred, every 2 weeks at least) and upload them to IPFS. Labs is to ensure the availability of this snapshot, either by directly hosting a node or by relying on a pinning service.

Snapshots should be listed in the snapshots index, stored in a well-known location (eg S3 bucket) hosted by Labs. Nodes will default to this S3 index, pick the latest snapshot, and use fast-sync by default.
