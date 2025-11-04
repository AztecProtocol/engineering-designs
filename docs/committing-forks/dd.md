# Intro

As part of the building in chunks project, it is desirable for nodes on the network to commit world state built from forks. The chain will advance independently of L1 for periods of time so the current model where state is only committed when recieved from L1 is insufficient.

## Current Architecture

Currently, committing forks is expressly forbidden by the world state. There is a strict model of:

1. A single, canconical fork, advanced solely by state read from L1. Tx effects are inserted to generate the new tree state in cache followed by a `commit_block` to persist the changes. This is performed by a `SYNC_BLOCK` request.
2. Any number of forks, taking any block as there reference. Any alternative chain state can be created but `commit_block` or any other persistance operation is prevented.

This strict model provides a strong guarantee that we only ever persist the true canonical state as well as removing a category of potential bugs around attempting to commit forks that don't refer to the last committed block.

```C++
template <typename LeafValueType>
void ContentAddressedCachedTreeStore<LeafValueType>::commit_block(TreeMeta& finalMeta, TreeDBStats& dbStats)
{
    // We don't allow commits using images/forks
    if (forkConstantData_.initialized_from_block_.has_value()) {
        throw std::runtime_error("Committing a fork is forbidden");
    }
    // ...Do the commit operation
}
```

Within the Typescript interface, operations are potentially queued before being sent to the NAPI. The queueing criteria is:

1. Each fork (including the canonical) has it's own queue.
2. Reads of committed state only bypass the queue. Read consistency is guaranteed by the MVCC nature of LMDB.
3. Reads of uncommitted state can occur concurrently with all other reads.
4. Writes of state (either to memory or disk) must be exclusive to other writes and reads of uncommitted state.

## Proposed Changes

Firstly, when a fork is created the roots of the trees of the canonical state will be captured and stored by the fork as `referenceRoot` values.

Secondly, a new request is introduced `COMMIT_FORK`. This will be considered a mutating request and will be queued as per the rules of other writes. The typescript interface will ensure that only a single `COMMIT_FORK` or `SYNC_BLOCK` request is in progress at a time.

The `COMMIT_FORK` request will first verify that the `referenceRoot` values match the current roots of the canonical state. Assuming the test is met, committing the cached state withing the fork will occur.

Finally, the fork will be deleted. Whilst not strictly necessary, long-lived forks should be discouraged as they accumulate memory. Creating new forks is extremely cheap.


