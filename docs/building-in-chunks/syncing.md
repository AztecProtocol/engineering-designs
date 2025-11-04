# Intro

How syncing the L2 chain works in a building-in-chunks world.

# Context

Nodes need to sync L2 block headers and block data. Block headers are eventually posted to L1 as calldata, whereas block data contains tx effects and are eventually posted as blobs.

We have the following potential channels for acquiring data:

- L1 calldata (for headers)
- L1 blobs (for tx effects)
- P2P gossipsub for broadcasting new data (either headers or tx effects)
- P2P reqresp for acquiring either headers or tx effects
- Centralized repositories (eg cloud-based file stores) for acquiring either headers or tx effects (blob archives only work for this when syncing mined or historical blocks, NOT for provisional blocks)
- Reconstructing tx effects via tx reexecution (assuming the tx hashes for the block are known via a proposal, and the original txs are available)

Note that acquiring L1 blobs require a supernode, so we want to avoid it if possible. Also note that block headers contain a commitment to tx effects, so if a node has a given block header, they can get the corresponding tx effects from any source and verify them.

Also note that headers are usually broadcasted along with the committee signatures, so any node can get an economic guarantee for the validity of a header by checking its attestations.

# Syncing historical blocks

A node that starts from scratch or has been offline may first download a snapshot archive to get a view of the chain no more than a day old, to speed up syncing.

Block headers should then be synced from L1 directly until the current tip of the L1-mined chain. For all block headers synced this way, the node should acquire its tx effects from:

- Any configured centralized repositories
- Any configured L1 supernode
- P2P reqresp (last resort in order to minimize pressure on the P2P layer)

# Syncing provisional blocks

Provisional blocks are not available on L1 by definition. Provisional block headers should be broadcasted across the network via gossipsub. As for provisional block data, we can:

- Have it submitted to centralized repositories (which means we upload block data when provisional, not mined) and sync from there
- Have validators in the committee (and nodes running with always-reexecute) sync from their current attestation job directly, assuming the provisional header matches
- Either include block data in the gossipsub'd block header, or have nodes rely on reqresp to obtain the block bodies that correspond to the headers

# Syncing mined blocks

Nodes monitor L1 for new mined blocks, and sync block headers from it. These block headers should match the provisional block headers already synced, in which case there is no need to sync new block data. If not, the provisional chain is reorged and the flow for syncing historical block data is used to obtain the missing data for any new blocks on L1.
